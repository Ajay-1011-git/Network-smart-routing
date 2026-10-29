from smartroute.baselines.scoring import FlapDamper, choose_routes, split_scorer
from smartroute.contracts import Decision


class ReactivePolicy:
    name = "reactive"

    def __init__(self, **scorer):
        self.scorer, damping = split_scorer(scorer)
        self.damper = FlapDamper(**damping)

    def reset(self):
        self.damper.reset()

    def decide(self, snapshot):
        return Decision(
            choose_routes(
                snapshot,
                {f.id: f.offered_bps for f in snapshot.flows},
                damper=self.damper,
                **self.scorer,
            ),
            (),
        )
