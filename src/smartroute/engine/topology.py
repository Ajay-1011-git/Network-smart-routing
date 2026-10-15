"""Validated, bounded local experiment catalog."""

import math
from dataclasses import asdict, replace

from smartroute.contracts import FlowSpec, LinkEvent, LinkSpec, RateSegment, RunConfig
from smartroute.engine.errors import ConfigurationError

TOPOLOGIES = ("diamond", "small-mesh")
SCENARIOS = ("steady", "ramp", "periodic", "spike", "capacity", "failure", "competing")


def validate_config(config):
    from smartroute.serialization import decode

    decode(RunConfig, asdict(config))

    def require(test, message):
        if not test:
            raise ConfigurationError(message)

    def unique(values, label):
        require(len(values) == len(set(values)) and all(values), f"Invalid {label} IDs")

    unique(config.nodes, "node")
    unique([link.id for link in config.links], "link")
    unique([flow.id for flow in config.flows], "flow")
    require(config.topology_id and config.scenario_id, "Missing catalog identifiers")
    require(
        config.measure_s > 0 and config.warmup_s >= 0 and config.drain_s >= 0,
        "Invalid run durations",
    )
    require(config.interval_s > 0 and config.horizon_s > 0, "Invalid control timing")
    end = config.warmup_s + config.measure_s
    for time in (config.warmup_s, config.measure_s, config.horizon_s):
        require(
            abs(time / config.interval_s - round(time / config.interval_s)) < 1e-8,
            "Durations/horizon must align to interval_s",
        )
    require(
        len(config.nodes) <= 64 and len(config.links) <= 512 and len(config.flows) <= 32,
        "Topology exceeds local simulator bounds",
    )
    require(end <= 3600 and end / config.interval_s <= 50000, "Run exceeds local bounds")
    pairs = set()
    for link in config.links:
        require(
            link.src in config.nodes and link.dst in config.nodes and link.src != link.dst,
            "Invalid link endpoints",
        )
        require((link.src, link.dst) not in pairs, "Parallel directed links are unsupported")
        pairs.add((link.src, link.dst))
        require(
            link.capacity_bps > 0 and link.propagation_s >= 0 and link.buffer_bytes >= 0,
            "Invalid link capacity/delay/buffer",
        )
    flow_ids = {flow.id for flow in config.flows}
    for flow in config.flows:
        require(
            flow.src in config.nodes and flow.dst in config.nodes and flow.src != flow.dst,
            "Invalid flow endpoints",
        )
        require(flow.packet_bytes > 0, "Packet size must be positive")
    prior = {}
    for segment in config.traffic:
        require(segment.flow_id in flow_ids, "Unknown segment flow")
        require(0 <= segment.start_s < segment.end_s <= end, "Invalid segment bounds")
        require(segment.start_s >= prior.get(segment.flow_id, 0), "Overlapping/unordered traffic")
        require(
            min(segment.start_bps, segment.end_bps) >= 0 and segment.period_s > 0,
            "Invalid traffic rate/period",
        )
        prior[segment.flow_id] = segment.end_s
    link_ids = {link.id for link in config.links}
    for event in config.events:
        require(event.link_id in link_ids and 0 <= event.time_s < end, "Invalid link event")
        require(
            abs(event.time_s / config.interval_s - round(event.time_s / config.interval_s)) < 1e-8,
            "Event must align to control grid",
        )
        require(
            (event.kind == "capacity" and event.value_bps is not None and event.value_bps > 0)
            or (event.kind != "capacity" and event.value_bps is None),
            "Invalid event capacity value",
        )
    return config


def catalog_config(
    topology="diamond",
    scenario="ramp",
    seed=0,
    load_multiplier=1.0,
    event_time_s=None,
    *,
    stress=False,
):
    if topology not in TOPOLOGIES or scenario not in SCENARIOS:
        raise ConfigurationError("Unknown topology/scenario; use catalog")
    if not math.isfinite(load_multiplier) or not 0.25 <= load_multiplier <= 2:
        raise ConfigurationError("Load multiplier must be in [0.25, 2]")
    nodes = ("S", "A", "B", "T") if topology == "diamond" else ("S", "A", "B", "C", "D", "T")
    edges = [("S", "A", 0.002), ("A", "T", 0.002), ("S", "B", 0.006), ("B", "T", 0.006)]
    if topology == "small-mesh":
        edges += [
            ("A", "C", 0.003),
            ("C", "T", 0.004),
            ("B", "D", 0.003),
            ("D", "T", 0.004),
            ("A", "B", 0.002),
            ("B", "A", 0.002),
            ("C", "D", 0.002),
            ("D", "C", 0.002),
        ]
    links = tuple(
        LinkSpec(f"{src}-{dst}", src, dst, 1_000_000.0, delay, 16000) for src, dst, delay in edges
    )
    flows = (FlowSpec("f0", "S", "T", 1000), FlowSpec("f1", "S", "T", 1000))
    end, start = 12.0, 4.0
    traffic = []
    for index, flow in enumerate(flows):
        scale = load_multiplier * (1.0 if index == 0 else 0.55)

        def seg(a, b, kind, low, high=None, period=3.0):
            traffic.append(
                RateSegment(
                    flow.id,
                    a,
                    b,
                    kind,
                    low * scale,
                    (low if high is None else high) * scale,
                    period,
                )
            )

        if scenario == "ramp":
            seg(0, end, "linear", 150000, 1300000)
        elif scenario == "periodic":
            seg(0, end, "periodic", 100000, 1200000)
        elif scenario == "spike":
            seg(0, start, "constant", 150000)
            seg(start, start + (1.2 if stress else 2.4), "constant", 1750000 if stress else 1150000)
            seg(start + (1.2 if stress else 2.4), end, "constant", 150000)
        else:
            seg(
                0,
                end,
                "constant",
                800000
                if scenario == "competing"
                else 550000
                if scenario in ("capacity", "failure")
                else 150000,
            )
    events = ()
    if scenario in ("capacity", "failure"):
        event_time = 4.0 if event_time_s is None else event_time_s
        if not 0 <= event_time <= 9.0:
            raise ConfigurationError("Event time must be in [0, 9] seconds")
        bottleneck = "A-T" if seed % 2 == 0 else "S-A"
        events = (
            LinkEvent(
                event_time,
                bottleneck,
                "capacity" if scenario == "capacity" else "down",
                220000.0 if scenario == "capacity" else None,
            ),
            LinkEvent(
                round(event_time + 2.0, 8),
                bottleneck,
                "capacity" if scenario == "capacity" else "up",
                1000000.0 if scenario == "capacity" else None,
            ),
        )
    elif event_time_s is not None:
        raise ConfigurationError("Event timing applies only to capacity/failure scenarios")
    return validate_config(
        RunConfig(
            topology,
            scenario,
            seed,
            nodes,
            links,
            flows,
            tuple(traffic),
            events,
            warmup_s=2.0,
            measure_s=10.0,
            drain_s=2.0,
        )
    )


def override_config(config, load_multiplier=1.0, event_time_s=None):
    if not 0.25 <= load_multiplier <= 2:
        raise ConfigurationError("Load multiplier must be in [0.25, 2]")
    traffic = tuple(
        replace(s, start_bps=s.start_bps * load_multiplier, end_bps=s.end_bps * load_multiplier)
        for s in config.traffic
    )
    events = config.events
    if event_time_s is not None:
        if not events:
            raise ConfigurationError("Configuration has no event to retime")
        delta = event_time_s - events[0].time_s
        events = tuple(replace(e, time_s=e.time_s + delta) for e in events)
    return validate_config(replace(config, traffic=traffic, events=events))
