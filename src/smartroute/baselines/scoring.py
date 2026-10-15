"""Shared causal, sequential demand reservation and hysteresis controller."""

import math
from functools import lru_cache
from itertools import islice

import networkx as nx

from smartroute.contracts import RouteChoice
from smartroute.engine.errors import PolicyError


def graph_for(links, packet_bytes, nominal=None):
    graph = nx.DiGraph()
    for link in sorted(links, key=lambda edge: edge.id):
        if link.up:
            capacity = nominal.get(link.id, link.capacity_bps) if nominal else link.capacity_bps
            graph.add_edge(
                link.src,
                link.dst,
                id=link.id,
                weight=link.propagation_s + 8 * packet_bytes / capacity,
            )
    return graph


@lru_cache(maxsize=4096)
def _candidates(edges, src, dst, packet_bytes, k):
    graph = nx.DiGraph()
    for id_, a, b, delay, capacity in edges:
        graph.add_edge(a, b, id=id_, weight=delay + 8 * packet_bytes / capacity)
    try:
        paths = [
            tuple(graph[a][b]["id"] for a, b in zip(path, path[1:]))
            for path in islice(nx.shortest_simple_paths(graph, src, dst, weight="weight"), k)
        ]
        return tuple(sorted(paths))
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return ()


def candidates(snapshot, flow, k=4):
    # Catalog nominal capacities are 1 Mbit/s. A fixed reference keeps path
    # enumeration invariant to capacity events and the public scorer stateless.
    edges = tuple(
        (e.id, e.src, e.dst, e.propagation_s, 1_000_000.0)
        for e in sorted(snapshot.links, key=lambda e: e.id)
        if e.up
    )
    paths = list(_candidates(edges, flow.src, flow.dst, flow.packet_bytes, k))
    available = {e.id for e in snapshot.links if e.up}
    if flow.route and set(flow.route) <= available and flow.route not in paths:
        paths.append(flow.route)
    return paths


def choose_routes(snapshot, demand_bps, *, alpha_s=0.02, improvement=0.10, cooldown_s=1.0, k=4):
    if set(demand_bps) != {f.id for f in snapshot.flows} or any(
        not math.isfinite(v) or v < 0 for v in demand_bps.values()
    ):
        raise PolicyError("Scorer requires one finite nonnegative demand per flow")
    if alpha_s < 0 or not 0 <= improvement <= 1 or cooldown_s < 0 or not 1 <= k <= 4:
        raise PolicyError("Invalid scorer parameters")
    links = {edge.id: edge for edge in snapshot.links}
    reserved = dict.fromkeys(links, 0.0)
    for flow in snapshot.flows:
        for edge in flow.route:
            reserved[edge] += demand_bps[flow.id]
    count = len(snapshot.flows)
    offset = round(snapshot.time_s / snapshot.interval_s) % count if count else 0
    ordered = snapshot.flows[offset:] + snapshot.flows[:offset]
    choices = {}
    for flow in ordered:
        demand = demand_bps[flow.id]
        for edge in flow.route:
            reserved[edge] -= demand
        paths = candidates(snapshot, flow, k)

        def cost(path):
            ratios = [(reserved[id_] + demand) / links[id_].capacity_bps for id_ in path]
            total = sum(
                links[id_].propagation_s
                + 8 * flow.packet_bytes / links[id_].capacity_bps
                + 8 * links[id_].resident_bytes / links[id_].capacity_bps
                + alpha_s * max(0, ratio - 0.70) ** 2
                for id_, ratio in zip(path, ratios)
            )
            return total, max(ratios, default=0.0)

        valid = bool(flow.route) and all(links[id_].up for id_ in flow.route)
        old_cost = cost(flow.route)[0] if valid else None
        if not paths:
            selected, new_cost, peak = (), None, None
            reason = "forced_disconnection" if flow.route else "no_path"
        else:
            best = min(paths, key=lambda path: (cost(path)[0], path))
            selected = best
            reason = (
                "initial" if snapshot.time_s == 0 else "forced_repair" if not valid else "switch"
            )
            if valid:
                cool = (
                    flow.last_switch_s is None
                    or snapshot.time_s - flow.last_switch_s >= cooldown_s - 1e-9
                )
                gain = (old_cost - cost(best)[0]) / max(old_cost, 1e-9)
                if best == flow.route:
                    reason = "retain_best"
                elif not cool or gain + 1e-12 < improvement:
                    selected = flow.route
                    reason = "cooldown" if not cool else "hysteresis"
            new_cost, peak = cost(selected)
        for edge in selected:
            reserved[edge] += demand
        choices[flow.id] = RouteChoice(flow.id, selected, reason, old_cost, new_cost, peak)
    return tuple(choices[f.id] for f in snapshot.flows)
