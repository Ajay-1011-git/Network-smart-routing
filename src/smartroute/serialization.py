"""Strict dataclass JSON, canonical digests and atomic persistence."""

import hashlib
import json
import math
import os
import tempfile
import types
from dataclasses import asdict, fields, is_dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Union, get_args, get_origin, get_type_hints

from smartroute.contracts import SCHEMA_VERSION, RunConfig, RunResult, Workload
from smartroute.engine.errors import ConfigurationError

_hints = lru_cache(maxsize=None)(get_type_hints)


def canonical(value):
    def normalized(item):
        if is_dataclass(item):
            return asdict(decode(type(item), asdict(item)))
        if isinstance(item, dict):
            return {key: normalized(val) for key, val in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalized(val) for val in item]
        return item

    return json.dumps(normalized(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def decode(cls, value):
    origin, args = get_origin(cls), get_args(cls)
    if origin in (Union, types.UnionType):
        for choice in args:
            try:
                return decode(choice, value)
            except ConfigurationError:
                pass
        raise ConfigurationError(f"Invalid optional value: {value!r}")
    if origin is Literal:
        if value not in args:
            raise ConfigurationError(f"Expected one of {args}: {value!r}")
        return value
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ConfigurationError("Expected array")
        return tuple(decode(args[0], item) for item in value)
    if is_dataclass(cls):
        if not isinstance(value, dict):
            raise ConfigurationError(f"Expected object for {cls.__name__}")
        expected = {f.name for f in fields(cls)}
        if set(value) != expected:
            raise ConfigurationError(f"{cls.__name__}: incorrect fields {set(value) ^ expected}")
        hints = _hints(cls)
        return cls(**{key: decode(hints[key], val) for key, val in value.items()})
    if cls is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ConfigurationError("Expected finite number")
        return float(value)
    if cls is type(None):
        if value is not None:
            raise ConfigurationError("Expected null")
        return None
    if type(value) is not cls:
        raise ConfigurationError(f"Expected {cls.__name__}, got {type(value).__name__}")
    return value


def atomic_json(value, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical(value)
    fd, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(data + "\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load(path, cls):
    try:
        obj = decode(cls, json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError) as exc:
        raise ConfigurationError(f"Cannot load {path}: {exc}") from exc
    if hasattr(obj, "schema_version") and obj.schema_version != SCHEMA_VERSION:
        raise ConfigurationError("Unsupported schema version")
    return obj


def save_config(config, path):
    from smartroute.engine.topology import validate_config

    validate_config(config)
    atomic_json(config, path)


def load_config(path):
    from smartroute.engine.topology import validate_config

    config = _load(path, RunConfig)
    validate_config(config)
    return config


def validate_workload(workload, config=None):
    from smartroute.engine.workload import trace_digest

    decode(Workload, asdict(workload))
    if workload.schema_version != SCHEMA_VERSION:
        raise ConfigurationError("Unsupported workload schema")
    seen, previous = set(), (-1.0, -1)
    flows = {f.id: f for f in config.flows} if config else None
    for packet in workload.packets:
        if packet.packet_id in seen or packet.packet_id < 0:
            raise ConfigurationError("Duplicate/negative packet ID")
        seen.add(packet.packet_id)
        order = (packet.generated_s, packet.packet_id)
        if order < previous or packet.generated_s < 0 or packet.size_bytes <= 0:
            raise ConfigurationError("Invalid packet order/time/size")
        previous = order
        if config and (
            packet.flow_id not in flows
            or packet.size_bytes != flows[packet.flow_id].packet_bytes
            or packet.generated_s >= config.warmup_s + config.measure_s
        ):
            raise ConfigurationError("Packet does not match configuration")
    if len(workload.trace_sha256) != 64:
        raise ConfigurationError("Invalid trace digest")
    if config and workload.trace_sha256 != trace_digest(workload.packets, config.events):
        raise ConfigurationError("Packet/event trace hash mismatch")


def save_workload(workload, path):
    validate_workload(workload)
    atomic_json(workload, path)


def load_workload(path):
    workload = _load(path, Workload)
    validate_workload(workload)
    return workload


def validate_result(result):
    from smartroute.engine.topology import validate_config

    decode(RunResult, asdict(result))
    validate_config(result.config)
    if result.schema_version != SCHEMA_VERSION or result.config_sha256 != digest(result.config):
        raise ConfigurationError("Result schema/config hash mismatch")
    if len(result.trace_sha256) != 64:
        raise ConfigurationError("Invalid result trace digest")
    ids = {p.packet_id for p in result.packets}
    flows = {f.id: f for f in result.config.flows}
    generation_stop = result.config.warmup_s + result.config.measure_s
    cutoff = generation_stop + result.config.drain_s
    if len(ids) != len(result.packets) or {f.flow_id for f in result.flow_metrics} != set(flows):
        raise ConfigurationError("Result packet/flow IDs are inconsistent")
    for packet in result.packets:
        if (
            packet.flow_id not in flows
            or packet.size_bytes != flows[packet.flow_id].packet_bytes
            or not 0 <= packet.generated_s < generation_stop
            or packet.route_version < 0
        ):
            raise ConfigurationError("Invalid packet outcome")
        if packet.status == "pending":
            if packet.terminal_s is not None or packet.drop_reason is not None:
                raise ConfigurationError("Pending packet has terminal information")
        elif packet.terminal_s is None or not packet.generated_s <= packet.terminal_s < cutoff:
            raise ConfigurationError("Invalid terminal time")
        if (packet.status == "dropped") != (packet.drop_reason is not None):
            raise ConfigurationError("Invalid drop reason")
    from smartroute.engine.metrics import compute_metrics

    metrics, flow_metrics = compute_metrics(
        result.config,
        result.packets,
        result.metrics.route_changes,
        result.metrics.forced_route_changes,
    )
    if result.metrics != metrics or result.flow_metrics != flow_metrics:
        raise ConfigurationError("Result metrics do not match packet ledger")
    if len(result.snapshots) != len(result.decisions):
        raise ConfigurationError("Snapshot/decision length mismatch")
    if len(result.snapshots) != round(generation_stop / result.config.interval_s):
        raise ConfigurationError("Missing control observations")
    from smartroute.contracts import TracePacket
    from smartroute.engine.workload import trace_digest

    trace = tuple(
        TracePacket(p.packet_id, p.flow_id, p.generated_s, p.size_bytes) for p in result.packets
    )
    if trace_digest(trace, result.config.events) != result.trace_sha256:
        raise ConfigurationError("Result packet/event trace mismatch")
    from smartroute.engine.sdk import validate_decision

    for index, (snap, record) in enumerate(zip(result.snapshots, result.decisions)):
        if snap.schema_version != SCHEMA_VERSION or snap.time_s != record.time_s:
            raise ConfigurationError("Invalid snapshot/decision alignment")
        if {link.id for link in snap.links} != {link.id for link in result.config.links}:
            raise ConfigurationError("Snapshot link references mismatch")
        if {flow.id for flow in snap.flows} != set(flows):
            raise ConfigurationError("Snapshot flow references mismatch")
        if record.runtime_ms < 0:
            raise ConfigurationError("Negative decision runtime")
        if (
            snap.time_s != round(index * result.config.interval_s, 12)
            or snap.interval_s != result.config.interval_s
            or snap.horizon_s != result.config.horizon_s
        ):
            raise ConfigurationError("Invalid control observation timing")
        for link, spec in zip(snap.links, result.config.links):
            if (
                (link.id, link.src, link.dst) != (spec.id, spec.src, spec.dst)
                or link.capacity_bps <= 0
                or link.propagation_s != spec.propagation_s
                or link.buffer_bytes != spec.buffer_bytes
                or not 0 <= link.resident_bytes <= link.buffer_bytes
                or min(
                    link.attempted_bits,
                    link.admitted_bits,
                    link.served_bits,
                    link.dropped_packets,
                    link.busy_s,
                )
                < 0
                or link.admitted_bits > link.attempted_bits
                or link.busy_s > snap.interval_s + 1e-8
            ):
                raise ConfigurationError("Invalid link telemetry")
        for flow, spec in zip(snap.flows, result.config.flows):
            if (
                (flow.id, flow.src, flow.dst, flow.packet_bytes)
                != (spec.id, spec.src, spec.dst, spec.packet_bytes)
                or flow.offered_bps < 0
                or (flow.last_switch_s is not None and not 0 <= flow.last_switch_s <= snap.time_s)
            ):
                raise ConfigurationError("Invalid source telemetry")
        try:
            validate_decision(snap, record.decision)
        except ValueError as exc:
            raise ConfigurationError(f"Invalid stored decision: {exc}") from exc


def save_result(result, path):
    validate_result(result)
    atomic_json(result, path)


def load_result(path):
    result = _load(path, RunResult)
    validate_result(result)
    return result
