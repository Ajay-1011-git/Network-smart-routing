"""Policy-independent, midpoint-integrated traffic with <=1 ms cells."""

import hashlib
import math
import random

from smartroute.contracts import SCHEMA_VERSION, TracePacket, Workload
from smartroute.engine.errors import ConfigurationError
from smartroute.engine.topology import validate_config
from smartroute.serialization import digest


def trace_digest(packets, events):
    return digest({"schema_version": SCHEMA_VERSION, "packets": packets, "events": events})


def rate_at(segment, time):
    if segment.kind == "constant":
        return segment.start_bps
    if segment.kind == "linear":
        fraction = (time - segment.start_s) / (segment.end_s - segment.start_s)
    else:
        fraction = (1 + math.sin(2 * math.pi * (time - segment.start_s) / segment.period_s)) / 2
    return segment.start_bps + (segment.end_bps - segment.start_bps) * fraction


def make_workload(config):
    validate_config(config)
    arrivals = []
    for flow in config.flows:
        seed = int.from_bytes(hashlib.sha256(f"{config.seed}:{flow.id}".encode()).digest()[:8])
        accumulated = random.Random(seed).random() * flow.packet_bytes * 8
        packet_bits = flow.packet_bytes * 8
        for segment in (s for s in config.traffic if s.flow_id == flow.id):
            count = math.ceil((segment.end_s - segment.start_s) / 0.001)
            dt = (segment.end_s - segment.start_s) / count
            for index in range(count):
                a = segment.start_s + index * dt
                rate = rate_at(segment, a + dt / 2)
                added = rate * dt
                while accumulated + added >= packet_bits and rate > 0:
                    needed = packet_bits - accumulated
                    a += needed / rate
                    added -= needed
                    accumulated = 0.0
                    if a < segment.end_s:
                        arrivals.append((a, flow.id, flow.packet_bytes))
                    if len(arrivals) > 250000:
                        raise ConfigurationError("Workload exceeds 250,000 packet local limit")
                accumulated += added
    arrivals.sort()
    packets = tuple(
        TracePacket(index, flow, time, size) for index, (time, flow, size) in enumerate(arrivals)
    )
    return Workload(SCHEMA_VERSION, trace_digest(packets, config.events), packets)
