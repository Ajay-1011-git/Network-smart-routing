"""Generation-cohort metrics. Never infer drops from unfinished packets."""

import numpy as np

from smartroute.contracts import FlowMetric, Metrics


def _summary(packets, duration):
    delivered = [p for p in packets if p.status == "delivered"]
    dropped = sum(p.status == "dropped" for p in packets)
    pending = sum(p.status == "pending" for p in packets)
    latencies = [p.terminal_s - p.generated_s for p in delivered]
    return (
        len(packets),
        len(delivered),
        dropped,
        pending,
        sum(p.size_bytes * 8 for p in delivered) / duration,
        float(np.mean(latencies)) if latencies else None,
        float(np.percentile(latencies, 95, method="linear")) if latencies else None,
    )


def compute_metrics(config, packets, route_changes=0, forced_changes=0):
    cohort = [
        p for p in packets if config.warmup_s <= p.generated_s < config.warmup_s + config.measure_s
    ]
    flows = tuple(
        FlowMetric(f.id, *_summary([p for p in cohort if p.flow_id == f.id], config.measure_s))
        for f in config.flows
    )
    n, delivered, dropped, pending, goodput, mean, p95 = _summary(cohort, config.measure_s)
    achieved = np.array([f.throughput_bps for f in flows if f.generated])
    fairness = (
        float(achieved.sum() ** 2 / (len(achieved) * (achieved**2).sum()))
        if len(achieved) and (achieved**2).sum()
        else None
    )
    return (
        Metrics(
            n,
            delivered,
            dropped,
            pending,
            delivered / n if n else None,
            dropped / n if n else None,
            goodput,
            mean,
            p95,
            fairness,
            route_changes,
            forced_changes,
        ),
        flows,
    )
