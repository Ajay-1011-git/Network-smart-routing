import networkx as nx

from smartroute.baselines.scoring import graph_for
from smartroute.contracts import Decision, RouteChoice


class StaticPolicy:
    name = "static"

    def __init__(self):
        self.reset()

    def reset(self):
        self.nominal = None

    def decide(self, snapshot):
        if self.nominal is None:
            self.nominal = {link.id: link.capacity_bps for link in snapshot.links}
        choices = []
        up = {link.id for link in snapshot.links if link.up}
        for flow in snapshot.flows:
            route = flow.route
            reason = "retain_static"
            if not route or not set(route) <= up:
                graph = graph_for(snapshot.links, flow.packet_bytes, self.nominal)
                try:
                    path = nx.shortest_path(graph, flow.src, flow.dst, weight="weight")
                    route = tuple(graph[a][b]["id"] for a, b in zip(path, path[1:]))
                    reason = "initial" if snapshot.time_s == 0 else "forced_repair"
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    route, reason = (), "forced_disconnection"
            choices.append(RouteChoice(flow.id, route, reason, None, None, None))
        return Decision(tuple(choices), ())
