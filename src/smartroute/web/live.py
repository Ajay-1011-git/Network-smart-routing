"""Incremental SimPy sessions sharing SmartRoute's packet data plane and scorer.

Interactive edits apply at control boundaries. Existing packet routes and queues
remain intact; the browser only renders observations and real wire-entry events.
"""

import hashlib
import math
import random
from collections import deque
from copy import deepcopy
from dataclasses import asdict, replace
from time import perf_counter

import simpy

from smartroute._vendor.ns_py.packet import Packet
from smartroute.baselines import ReactivePolicy, StaticPolicy
from smartroute.contracts import (
    SCHEMA_VERSION,
    FlowObservation,
    FlowSpec,
    LinkSpec,
    PacketOutcome,
    RunConfig,
    Snapshot,
)
from smartroute.engine.adapter import LinkAdapter
from smartroute.engine.errors import ConfigurationError, EngineError
from smartroute.engine.metrics import compute_metrics
from smartroute.engine.sdk import _at, validate_decision
from smartroute.engine.topology import validate_config

DEVICE_TYPES = {"router", "switch", "computer", "server", "cloud"}
POLICIES = {"reactive", "static", "predictive-trend", "predictive-learned"}


def number(value, low, high, name):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ConfigurationError(f"{name} must be a finite number between {low:g} and {high:g}")
    return float(value)


def identifier(value, name):
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ConfigurationError(f"Invalid {name}")
    if any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        for char in value
    ):
        raise ConfigurationError(f"{name} may contain letters, numbers, underscores and hyphens")
    return value


def validate_graph(data):
    if not isinstance(data, dict):
        raise ConfigurationError("Expected a network object")
    for key, limit in (("nodes", 32), ("connections", 64), ("flows", 8)):
        if not isinstance(data.get(key), list) or len(data[key]) > limit:
            raise ConfigurationError(f"{key} must be an array with at most {limit} entries")
    nodes, connections, flows = data["nodes"], data["connections"], data["flows"]
    if len(nodes) < 2 or not flows:
        raise ConfigurationError("Add at least two devices and one traffic flow before starting")
    ids, pairs, cable_ids, flow_ids = set(), set(), set(), set()
    for node in nodes:
        node_id = identifier(node.get("id"), "device ID")
        if node_id in ids or node.get("kind") not in DEVICE_TYPES:
            raise ConfigurationError("Duplicate device ID or unsupported device type")
        ids.add(node_id)
        if not isinstance(node.get("label"), str) or not 1 <= len(node["label"].strip()) <= 64:
            raise ConfigurationError("Device names must contain 1–64 characters")
        pos = node.get("position", {})
        number(pos.get("x"), -100000, 100000, "Device x position")
        number(pos.get("y"), -100000, 100000, "Device y position")
    for connection in connections:
        cable_id = identifier(connection.get("id"), "connection ID")
        a, b = connection.get("source"), connection.get("target")
        if (
            a not in ids
            or b not in ids
            or a == b
            or frozenset((a, b)) in pairs
            or cable_id in cable_ids
        ):
            raise ConfigurationError(
                "Connections need distinct known devices; parallel cables are unsupported"
            )
        pairs.add(frozenset((a, b)))
        cable_ids.add(cable_id)
        number(connection.get("capacity_mbps"), 0.01, 1000, "Connection capacity (Mbit/s)")
        number(connection.get("latency_ms", 5), 0, 1000, "Propagation delay (ms)")
        buffer = connection.get("buffer_bytes", 64000)
        if type(buffer) is not int or not 0 <= buffer <= 1000000:
            raise ConfigurationError("Buffer size must be an integer between 0 and 1,000,000 bytes")
        if type(connection.get("up", True)) is not bool:
            raise ConfigurationError("Connection availability must be boolean")
    for flow in flows:
        flow_id = identifier(flow.get("id"), "flow ID")
        if (
            flow_id in flow_ids
            or flow.get("source") not in ids
            or flow.get("target") not in ids
            or flow["source"] == flow["target"]
        ):
            raise ConfigurationError(
                "Flows need unique IDs and distinct known source/destination devices"
            )
        flow_ids.add(flow_id)
        number(flow.get("rate_mbps"), 0, 10, "Source traffic (Mbit/s)")
        size = flow.get("packet_bytes", 1000)
        if type(size) is not int or not 64 <= size <= 9000:
            raise ConfigurationError("Packet size must be an integer between 64 and 9000 bytes")
    policy = data.get("policy", "reactive")
    if policy not in POLICIES:
        raise ConfigurationError("Unsupported routing policy")
    return data


class LiveSession:
    interval_s = 0.2
    max_seconds = 300
    max_packets = 200000

    def __init__(self, graph):
        self.graph = deepcopy(validate_graph(graph))
        self.env = simpy.Environment()
        self.tick = 0
        self.sequence = 0
        self.routes = {flow["id"]: () for flow in graph["flows"]}
        self.versions = dict.fromkeys(self.routes, 0)
        self.switches = dict.fromkeys(self.routes)
        self.offered = dict.fromkeys(self.routes, 0)
        self.rates = {flow["id"]: flow["rate_mbps"] * 1e6 for flow in graph["flows"]}
        self.credits = {
            flow["id"]: random.Random(
                int.from_bytes(hashlib.sha256(flow["id"].encode()).digest()[:8])
            ).random()
            * flow.get("packet_bytes", 1000)
            * 8
            for flow in graph["flows"]
        }
        self.cables = {c["id"]: deepcopy(c) for c in graph["connections"]}
        specs = []
        for cable in graph["connections"]:
            for suffix, source, target in (
                ("fwd", cable["source"], cable["target"]),
                ("rev", cable["target"], cable["source"]),
            ):
                specs.append(
                    LinkSpec(
                        f"{cable['id']}:{suffix}",
                        source,
                        target,
                        cable["capacity_mbps"] * 1e6,
                        cable.get("latency_ms", 5) / 1000,
                        cable.get("buffer_bytes", 64000),
                    )
                )
        flows = tuple(
            FlowSpec(f["id"], f["source"], f["target"], f.get("packet_bytes", 1000))
            for f in graph["flows"]
        )
        self.config = validate_config(
            RunConfig(
                "custom",
                "interactive",
                0,
                tuple(n["id"] for n in graph["nodes"]),
                tuple(specs),
                flows,
                (),
                (),
                warmup_s=0.0,
                measure_s=300.0,
                drain_s=0.0,
            )
        )
        self.outcomes, self.packet_states = {}, {}
        self.route_changes = self.forced_changes = 0
        self.transmissions = []
        self.events = deque(maxlen=150)
        self.history = deque(maxlen=150)
        self.edit_log = []
        self.latest_snapshot = None
        self.latest_decision = None
        self.links = {}
        for spec in specs:
            link = LinkAdapter(self.env, spec, self._advance_packet, self._terminal)
            original = link.egress

            def egress(packet, edge=link, callback=original):
                if edge.up:
                    self.transmissions.append(
                        {
                            "packet_id": packet.packet_id,
                            "flow_id": packet.flow_id,
                            "link_id": edge.spec.id,
                            "source": edge.spec.src,
                            "target": edge.spec.dst,
                            "time_s": self.env.now,
                            "arrival_s": self.env.now + edge.spec.propagation_s,
                            "route_version": self.outcomes[packet.packet_id].route_version,
                        }
                    )
                callback(packet)

            link.port.out.put = egress
            link.up = self.cables[spec.id.rsplit(":", 1)[0]].get("up", True)
            self.links[spec.id] = link
        name = graph.get("policy", "reactive")
        if name == "static":
            self.policy = StaticPolicy()
        elif name == "reactive":
            self.policy = ReactivePolicy()
        else:
            from pathlib import Path

            from smartroute.intelligence.policy import PredictivePolicy

            self.policy = PredictivePolicy(
                name.removeprefix("predictive-"),
                Path(__file__).resolve().parents[3] / "models/selected",
            )
        self.policy.reset()

    def _terminal(self, packet, reason=None):
        old = self.outcomes[packet.packet_id]
        if old.status != "pending":
            raise EngineError("Interactive packet completed twice")
        self.outcomes[packet.packet_id] = replace(
            old,
            status="dropped" if reason else "delivered",
            terminal_s=self.env.now,
            drop_reason=reason,
        )
        self.packet_states.pop(packet.packet_id, None)

    def _advance_packet(self, packet):
        path, hop = self.packet_states[packet.packet_id]
        if hop == len(path):
            self._terminal(packet)
        else:
            self.packet_states[packet.packet_id] = path, hop + 1
            self.links[path[hop]].put(packet)

    def _generate(self, flow, time):
        if self.sequence >= self.max_packets:
            raise ConfigurationError(
                "Live packet budget reached. Reset the simulation to continue."
            )
        packet_id = self.sequence
        self.sequence += 1
        self.offered[flow.id] += flow.packet_bytes * 8
        self.outcomes[packet_id] = PacketOutcome(
            packet_id,
            flow.id,
            time,
            flow.packet_bytes,
            "pending",
            None,
            None,
            self.versions[flow.id],
        )
        packet = Packet(time, flow.packet_bytes, packet_id, flow_id=flow.id)
        path = self.routes[flow.id]
        if not path:
            self._terminal(packet, "no_route")
        else:
            self.packet_states[packet_id] = path, 0
            self._advance_packet(packet)

    def _control(self):
        time = self.env.now
        self.latest_snapshot = Snapshot(
            SCHEMA_VERSION,
            time,
            self.interval_s,
            1.0,
            tuple(
                link.observe(max(0.0, time - self.interval_s), time) for link in self.links.values()
            ),
            tuple(
                FlowObservation(
                    f.id,
                    f.src,
                    f.dst,
                    f.packet_bytes,
                    self.offered[f.id] / self.interval_s,
                    self.routes[f.id],
                    self.switches[f.id],
                )
                for f in self.config.flows
            ),
        )
        started = perf_counter()
        decision = self.policy.decide(self.latest_snapshot)
        self.runtime_ms = (perf_counter() - started) * 1000
        validate_decision(self.latest_snapshot, decision)
        for choice in decision.routes:
            old = self.routes[choice.flow_id]
            if old != choice.link_ids:
                forced = (
                    not old or not choice.link_ids or any(not self.links[id_].up for id_ in old)
                )
                if self.tick:
                    self.route_changes += 1
                    self.forced_changes += int(forced)
                    self.switches[choice.flow_id] = time
                self.versions[choice.flow_id] += 1
                self.routes[choice.flow_id] = choice.link_ids
                self.events.appendleft(
                    {
                        "time_s": time,
                        "flow_id": choice.flow_id,
                        "old_route": list(old),
                        "new_route": list(choice.link_ids),
                        "reason": choice.reason,
                        "forced": forced if self.tick else False,
                        "old_cost_s": choice.old_cost_s,
                        "new_cost_s": choice.new_cost_s,
                        "projected_peak_load": choice.projected_peak_load,
                    }
                )
        self.latest_decision = decision
        for flow_id in self.offered:
            self.offered[flow_id] = 0

    def apply(self, changes):
        if not isinstance(changes, dict):
            raise ConfigurationError("Expected live controls object")
        if not isinstance(changes.get("rates", {}), dict) or not isinstance(
            changes.get("connections", {}), dict
        ):
            raise ConfigurationError("Invalid traffic/connection controls")
        validated_rates, validated_cables = {}, {}
        for flow_id, rate in changes.get("rates", {}).items():
            if flow_id not in self.rates:
                raise ConfigurationError("Unknown traffic flow")
            validated_rates[flow_id] = number(rate, 0, 10, "Source traffic (Mbit/s)") * 1e6
        for cable_id, controls in changes.get("connections", {}).items():
            if cable_id not in self.cables or not isinstance(controls, dict):
                raise ConfigurationError("Unknown connection")
            if type(controls.get("up", self.cables[cable_id].get("up", True))) is not bool:
                raise ConfigurationError("Connection availability must be boolean")
            capacity = number(
                controls.get("capacity_mbps", self.cables[cable_id]["capacity_mbps"]),
                0.01,
                1000,
                "Connection capacity (Mbit/s)",
            )
            validated_cables[cable_id] = (
                capacity,
                controls.get("up", self.cables[cable_id].get("up", True)),
            )
        # Validate the entire command before mutating a running session.
        for flow_id, rate in validated_rates.items():
            self.rates[flow_id] = rate
        for cable_id, (capacity, up) in validated_cables.items():
            self.cables[cable_id]["capacity_mbps"] = capacity
            self.cables[cable_id]["up"] = up
            for suffix in ("fwd", "rev"):
                link = self.links[f"{cable_id}:{suffix}"]
                link.up = up
                link.capacity = link.port.rate = capacity * 1e6
        if changes.get("rates") or changes.get("connections"):
            self.edit_log.append(
                {
                    "time_s": self.env.now,
                    "rates_bps": validated_rates,
                    "connections": {
                        key: {"capacity_mbps": value[0], "up": value[1]}
                        for key, value in validated_cables.items()
                    },
                }
            )

    def step(self, changes=None):
        if self.env.now >= self.max_seconds:
            raise ConfigurationError("Five-minute live session limit reached. Reset to continue.")
        self.apply(changes or {})
        self.transmissions = []
        start, end = self.env.now, round((self.tick + 1) * self.interval_s, 12)
        _at(self.env, start, -2, self._control)
        for flow in self.config.flows:
            rate, bits = self.rates[flow.id], flow.packet_bytes * 8
            if not rate:
                continue
            credit = self.credits[flow.id]
            offset = max(0.0, (bits - credit) / rate)
            emitted = 0
            while offset < self.interval_s - 1e-12:
                time = start + offset
                _at(self.env, time, 2, lambda f=flow, t=time: self._generate(f, t))
                offset += bits / rate
                emitted += 1
            # A packet due exactly at the next control boundary belongs to the
            # next interval. Preserve a whole packet of credit rather than
            # reducing modulo bits and losing it at every boundary.
            self.credits[flow.id] = max(0.0, credit + rate * self.interval_s - emitted * bits)
        self.env.run(until=end)
        self.tick += 1
        observation = self.payload()
        self.history.append(
            {
                "time_s": end,
                "offered_mbps": sum(self.rates.values()) / 1e6,
                "goodput_mbps": observation["metrics"]["throughput_bps"] / 1e6,
                "pending": observation["metrics"]["pending"],
                "route_changes": self.route_changes,
            }
        )
        observation["history"] = list(self.history)
        return observation

    def payload(self):
        metrics, flow_metrics = compute_metrics(
            replace(self.config, measure_s=max(self.env.now, self.interval_s)),
            tuple(self.outcomes.values()),
            self.route_changes,
            self.forced_changes,
        )
        return {
            "time_s": self.env.now,
            "tick": self.tick,
            "policy": self.policy.name,
            "snapshot": asdict(self.latest_snapshot) if self.latest_snapshot else None,
            "decision": asdict(self.latest_decision) if self.latest_decision else None,
            "metrics": asdict(metrics),
            "flow_metrics": [asdict(f) for f in flow_metrics],
            "rates_bps": self.rates.copy(),
            "events": list(self.events),
            "transmissions": self.transmissions[-120:],
            "decision_runtime_ms": getattr(self, "runtime_ms", 0),
            "history": list(self.history),
        }

    def export(self):
        return {
            "kind": "smartroute-interactive-session",
            "schema_version": "1.0",
            "network": self.graph,
            "edits": self.edit_log,
            "state": self.payload(),
            "packets": [asdict(p) for p in self.outcomes.values()],
            "semantics": "Live generation cohort [0,time_s); pending packets remain pending. No final drain.",
        }
