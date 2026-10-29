"""Shared causal, sequential demand reservation, hysteresis and flap-damping controller."""

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


class FlapDamper:
    """Exponential hold-down for route reversals, in the spirit of BGP flap damping.

    Returning a flow to a path it voluntarily left is a reversal. A reversal is allowed
    only after the flow has stayed on its current path for hold_s * 2**penalty seconds
    (capped at max_hold_s); each reversal adds one to the penalty, which halves every
    half_life_s. A reversal is damped only while the current path's projected peak load is
    at most max_load, so a flow is never held on a path it is overloading. Forced repairs never consult or update the damper, so failover and the
    return to a restored path are unaffected. hold_s=0 disables damping.
    """

    def __init__(self, hold_s=0.0, half_life_s=10.0, max_hold_s=16.0, max_load=1.0):
        if hold_s < 0 or half_life_s <= 0 or max_hold_s < hold_s or max_load < 0:
            raise PolicyError("Invalid flap damping parameters")
        self.hold_s, self.half_life_s, self.max_hold_s = hold_s, half_life_s, max_hold_s
        self.max_load = max_load
        self.reset()

    def reset(self):
        self.left = {}
        self.penalty = {}

    def _penalty(self, flow_id, now):
        value, since = self.penalty.get(flow_id, (0.0, now))
        return value * 0.5 ** ((now - since) / self.half_life_s)

    def allows(self, flow, route, now, current_load):
        if (
            not self.hold_s
            or current_load > self.max_load + 1e-12
            or route not in self.left.get(flow.id, ())
        ):
            return True
        hold = min(self.max_hold_s, self.hold_s * 2 ** self._penalty(flow.id, now))
        since = flow.last_switch_s if flow.last_switch_s is not None else -math.inf
        return now - since >= hold - 1e-9

    def record(self, flow, route, now):
        if not self.hold_s or route == flow.route:
            return
        if route in self.left.get(flow.id, ()):
            self.penalty[flow.id] = (self._penalty(flow.id, now) + 1.0, now)
        self.left.setdefault(flow.id, set()).add(flow.route)


# Selected on validation seeds only; see docs/DECISIONS.md. Scorer dictionaries may
# override these with flap_hold_s, flap_half_life_s and flap_max_hold_s.
DAMPING_DEFAULTS = {
    "flap_hold_s": 8.0,
    "flap_half_life_s": 15.0,
    "flap_max_hold_s": 16.0,
    "flap_max_load": 1.0,
}


def split_scorer(scorer):
    """Separate choose_routes parameters from FlapDamper parameters."""
    damping = {**DAMPING_DEFAULTS, **{k: v for k, v in scorer.items() if k in DAMPING_DEFAULTS}}
    rest = {k: v for k, v in scorer.items() if k not in DAMPING_DEFAULTS}
    return rest, {key.removeprefix("flap_"): value for key, value in damping.items()}


def choose_routes(
    snapshot, demand_bps, *, alpha_s=0.02, improvement=0.10, cooldown_s=1.0, k=4, damper=None
):
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
                elif damper is not None and not damper.allows(
                    flow, best, snapshot.time_s, cost(flow.route)[1]
                ):
                    selected = flow.route
                    reason = "flap_damping"
                elif damper is not None:
                    damper.record(flow, best, snapshot.time_s)
            new_cost, peak = cost(selected)
        for edge in selected:
            reserved[edge] += demand
        choices[flow.id] = RouteChoice(flow.id, selected, reason, old_cost, new_cost, peak)
    return tuple(choices[f.id] for f in snapshot.flows)
