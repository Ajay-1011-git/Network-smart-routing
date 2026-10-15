from smartroute.baselines.scoring import choose_routes
from smartroute.contracts import Decision


class ReactivePolicy:
    name = "reactive"

    def __init__(self, **scorer):
        self.scorer = scorer

    def reset(self):
        pass

    def decide(self, snapshot):
        return Decision(
            choose_routes(snapshot, {f.id: f.offered_bps for f in snapshot.flows}, **self.scorer),
            (),
        )
