"""Identical causal feature extraction for offline training and online inference."""

import numpy as np

from smartroute.serialization import digest

FEATURE_NAMES = tuple(
    [f"lag_{i}" for i in range(9, -1, -1)]
    + [f"difference_{i}" for i in range(9)]
    + ["mean", "std", "slope"]
)
FEATURE_HASH = digest(FEATURE_NAMES)


def features(history, interval_s):
    if len(history) < 10:
        return None
    if interval_s <= 0:
        raise ValueError("Invalid observation interval")
    values = np.asarray(history[-10:], dtype=float) / 1_000_000
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Invalid rate history")
    slope = np.polyfit(np.arange(10) * interval_s, values, 1)[0]
    return np.concatenate((values, np.diff(values), [values.mean(), values.std(), slope]))


def trend_rate(history, interval_s, horizon_s):
    current = history[-1] if history else 0.0
    if len(history) < 10:
        return current
    values = np.asarray(history[-5:])
    slope = np.polyfit(np.arange(len(values)) * interval_s, values, 1)[0]
    return float(
        np.clip(
            values[-1] + slope * (horizon_s + interval_s) / 2, 0.0, max(current * 3.0, 100000.0)
        )
    )


class History:
    def __init__(self):
        self.rates = {}
        self.previous = None

    def update(self, snapshot):
        if snapshot.schema_version != "1.0":
            raise ValueError("Unsupported snapshot schema")
        if (
            self.previous is not None
            and abs(snapshot.time_s - self.previous - snapshot.interval_s) > 1e-7
        ):
            raise ValueError("Missing/out-of-order observation window")
        ids = {flow.id for flow in snapshot.flows}
        if self.rates and set(self.rates) != ids:
            raise ValueError("Flow set changed during run")
        self.previous = snapshot.time_s
        for flow in snapshot.flows:
            history = self.rates.setdefault(flow.id, [])
            if snapshot.time_s > 0:
                history.append(flow.offered_bps)
                del history[:-10]
