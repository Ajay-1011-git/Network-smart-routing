"""One fresh SimPy environment per run; policies receive only Snapshot."""

from dataclasses import asdict, replace
from time import perf_counter

import networkx as nx
import simpy

from smartroute._vendor.ns_py.packet import Packet
from smartroute.contracts import (
    SCHEMA_VERSION,
    Decision,
    DecisionRecord,
    FlowObservation,
    PacketOutcome,
    RunResult,
    Snapshot,
)
from smartroute.engine.adapter import LinkAdapter
from smartroute.engine.errors import EngineError, PolicyError
from smartroute.engine.metrics import compute_metrics
from smartroute.engine.topology import validate_config
from smartroute.engine.workload import make_workload
from smartroute.serialization import decode, digest, validate_workload


def _at(env, time, priority, callback):
    event = simpy.Event(env)
    event._ok, event._value = True, None
    event.callbacks.append(lambda _: callback())
    env.schedule(event, priority=priority, delay=time - env.now)


def validate_decision(snapshot, decision):
    try:
        decode(Decision, asdict(decision))
    except (ValueError, TypeError) as exc:
        raise PolicyError(f"Malformed policy decision: {exc}") from exc
    flows = {flow.id: flow for flow in snapshot.flows}
    links = {link.id: link for link in snapshot.links}
    if len(decision.routes) != len(flows) or {r.flow_id for r in decision.routes} != set(flows):
        raise PolicyError("Decision must cover each flow exactly once")
    graph = nx.DiGraph()
    graph.add_nodes_from({f.src for f in snapshot.flows} | {f.dst for f in snapshot.flows})
    graph.add_edges_from((link.src, link.dst) for link in snapshot.links if link.up)
    for route in decision.routes:
        flow = flows[route.flow_id]
        if not route.link_ids:
            if nx.has_path(graph, flow.src, flow.dst):
                raise PolicyError("Empty route despite feasible path")
            continue
        node, visited = flow.src, {flow.src}
        for id_ in route.link_ids:
            edge = links.get(id_)
            if edge is None or not edge.up or edge.src != node or edge.dst in visited:
                raise PolicyError(f"Invalid/cyclic/unavailable route for {flow.id}")
            node = edge.dst
            visited.add(node)
        if node != flow.dst:
            raise PolicyError("Route does not reach destination")
        if any(
            value is not None and value < 0
            for value in (route.old_cost_s, route.new_cost_s, route.projected_peak_load)
        ):
            raise PolicyError("Negative route cost/load")
    if decision.forecasts:
        if len(decision.forecasts) != len(flows) or {f.flow_id for f in decision.forecasts} != set(
            flows
        ):
            raise PolicyError("Forecast coverage mismatch")
        for forecast in decision.forecasts:
            if (
                forecast.rate_bps < 0
                or forecast.issued_s != snapshot.time_s
                or forecast.horizon_s != snapshot.horizon_s
            ):
                raise PolicyError("Invalid forecast rate/time/horizon")


class SimulationEngine:
    make_workload = staticmethod(make_workload)

    def run(self, config, workload, policy):
        validate_config(config)
        validate_workload(workload, config)
        env = simpy.Environment()
        routes = {f.id: () for f in config.flows}
        switches = dict.fromkeys(routes)
        versions = dict.fromkeys(routes, 0)
        offered = dict.fromkeys(routes, 0)
        outcomes, states, snapshots, decisions = {}, {}, [], []
        changes = [0, 0]

        def terminal(packet, reason=None):
            previous = outcomes[packet.packet_id]
            if previous.status != "pending":
                raise EngineError("Packet reached two terminal states")
            outcomes[packet.packet_id] = replace(
                previous,
                status="dropped" if reason else "delivered",
                terminal_s=env.now,
                drop_reason=reason,
            )

        def advance(packet):
            state = states[packet.packet_id]
            path, hop = state
            if hop == len(path):
                terminal(packet)
            else:
                states[packet.packet_id] = (path, hop + 1)
                links[path[hop]].put(packet)

        links = {spec.id: LinkAdapter(env, spec, advance, terminal) for spec in config.links}
        event_ticks = {}
        for event in config.events:
            event_ticks.setdefault(round(event.time_s / config.interval_s), []).append(event)
        policy.reset()

        def control(index):
            time = round(index * config.interval_s, 12)
            for event in event_ticks.get(index, ()):
                link = links[event.link_id]
                if event.kind == "capacity":
                    link.capacity = link.port.rate = event.value_bps
                else:
                    link.up = event.kind == "up"
            start = max(0.0, time - config.interval_s)
            snapshot = Snapshot(
                SCHEMA_VERSION,
                time,
                config.interval_s,
                config.horizon_s,
                tuple(link.observe(start, time) for link in links.values()),
                tuple(
                    FlowObservation(
                        f.id,
                        f.src,
                        f.dst,
                        f.packet_bytes,
                        offered[f.id] / config.interval_s,
                        routes[f.id],
                        switches[f.id],
                    )
                    for f in config.flows
                ),
            )
            begun = perf_counter()
            decision = policy.decide(snapshot)
            elapsed = (perf_counter() - begun) * 1000
            validate_decision(snapshot, decision)
            for choice in decision.routes:
                old = routes[choice.flow_id]
                if old != choice.link_ids:
                    if index:
                        changes[0] += 1
                        if not old or not choice.link_ids or any(not links[id_].up for id_ in old):
                            changes[1] += 1
                        switches[choice.flow_id] = time
                    versions[choice.flow_id] += 1
                    routes[choice.flow_id] = choice.link_ids
            snapshots.append(snapshot)
            decisions.append(DecisionRecord(time, elapsed, decision))
            for flow_id in offered:
                offered[flow_id] = 0

        def generate(trace):
            offered[trace.flow_id] += trace.size_bytes * 8
            outcomes[trace.packet_id] = PacketOutcome(
                trace.packet_id,
                trace.flow_id,
                trace.generated_s,
                trace.size_bytes,
                "pending",
                None,
                None,
                versions[trace.flow_id],
            )
            packet = Packet(
                trace.generated_s, trace.size_bytes, trace.packet_id, flow_id=trace.flow_id
            )
            path = routes[trace.flow_id]
            if not path:
                terminal(packet, "no_route")
            else:
                states[trace.packet_id] = (path, 0)
                advance(packet)

        stop = config.warmup_s + config.measure_s
        for index in range(round(stop / config.interval_s)):
            _at(env, round(index * config.interval_s, 12), -2, lambda i=index: control(i))
        for trace in workload.packets:
            _at(env, trace.generated_s, 2, lambda p=trace: generate(p))
        env.run(until=stop + config.drain_s)
        packets = tuple(outcomes[p.packet_id] for p in workload.packets)
        metrics, flow_metrics = compute_metrics(config, packets, *changes)
        return RunResult(
            SCHEMA_VERSION,
            digest(config),
            workload.trace_sha256,
            policy.name,
            config,
            metrics,
            flow_metrics,
            tuple(snapshots),
            tuple(decisions),
            packets,
        )
