import numpy as np

from smartroute.baselines.scoring import choose_routes
from smartroute.contracts import Decision, Forecast
from smartroute.intelligence.features import History, features, trend_rate
from smartroute.intelligence.model_io import load_model


class PredictivePolicy:
    def __init__(self, predictor="persistence", model="models/selected", **scorer):
        if predictor not in ("persistence", "trend", "learned"):
            raise ValueError("Unknown predictor")
        self.predictor, self.scorer = predictor, scorer
        self.name = f"predictive-{predictor}"
        self.estimator, self.metadata = load_model(model) if predictor == "learned" else (None, {})
        self.reset()

    def reset(self):
        self.history = History()

    def decide(self, snapshot):
        if self.predictor == "learned" and (
            snapshot.interval_s != self.metadata["observation_interval_s"]
            or snapshot.horizon_s != self.metadata["horizon_s"]
        ):
            raise ValueError("Learned model requires its trained observation interval and horizon")
        self.history.update(snapshot)
        forecasts = []
        for flow in snapshot.flows:
            history = self.history.rates[flow.id]
            vector = features(history, snapshot.interval_s)
            rate, status, reason = flow.offered_bps, "persistence", "current observed source rate"
            if vector is None:
                reason = "warm-up: fewer than 10 completed observation windows"
            elif self.predictor == "trend":
                rate = trend_rate(history, snapshot.interval_s, snapshot.horizon_s)
                status, reason = "trend", "clipped causal five-window linear trend"
            elif self.predictor == "learned":
                lower, upper = (
                    np.array(self.metadata["support_min"]),
                    np.array(self.metadata["support_max"]),
                )
                margin = 0.05 * np.maximum(upper - lower, 0.02)
                if ((vector < lower - margin) | (vector > upper + margin)).any():
                    status, reason = "fallback", "outside train/validation feature support"
                else:
                    predicted = float(self.estimator.predict(vector.reshape(1, -1))[0]) * 1_000_000
                    if (
                        not np.isfinite(predicted)
                        or predicted < 0
                        or predicted > self.metadata["rate_ceiling_bps"]
                    ):
                        status, reason = "fallback", "invalid or unsupported learned output"
                    else:
                        rate, status, reason = (
                            predicted,
                            "model",
                            "learned forward-mean source rate",
                        )
            forecasts.append(
                Forecast(
                    flow.id,
                    snapshot.time_s,
                    snapshot.horizon_s,
                    float(rate),
                    self.metadata.get("model_sha256", self.predictor),
                    status,
                    reason,
                )
            )
        choices = choose_routes(snapshot, {f.flow_id: f.rate_bps for f in forecasts}, **self.scorer)
        return Decision(choices, tuple(forecasts))
