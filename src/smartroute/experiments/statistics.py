"""Paired seed-block bootstrap intervals over audited run-level summaries.

A seed block is every topology/scenario run that shares one workload seed. Policies are
compared inside a block on identical traces; blocks, not packets or ticks, are resampled.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from smartroute.serialization import atomic_json

DRAWS = 20_000
RNG_SEED = 20261029
COMPARISONS = (
    ("reactive", "static"),
    ("predictive-trend", "static"),
    ("predictive-learned", "static"),
    ("predictive-trend", "reactive"),
    ("predictive-learned", "reactive"),
    ("predictive-learned", "predictive-trend"),
)


def _blocks(frame, policy, metric):
    rows = frame[(frame.policy == policy) & (frame.variant == "default")]
    table = rows.pivot_table(
        index="seed", columns=["topology", "scenario"], values=metric, aggfunc="first"
    )
    if table.isna().any().any():
        raise ValueError(f"Missing or null {metric} for {policy}")
    return table.sort_index().sort_index(axis=1)


def _interval(values, rng):
    values = np.asarray(values, dtype=float)
    draws = rng.integers(0, len(values), size=(DRAWS, len(values)))
    means = values[draws].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(values.mean()), float(low), float(high)


def paired_statistics(frame, metric="delivery_ratio"):
    """Return policy means and paired candidate-minus-baseline deltas with 95% CIs."""
    policies = sorted(frame.policy.unique())
    tables = {policy: _blocks(frame, policy, metric) for policy in policies}
    shapes = {table.shape for table in tables.values()}
    if len(shapes) != 1 or any(
        not table.index.equals(tables[policies[0]].index) for table in tables.values()
    ):
        raise ValueError("Policies do not cover the same seed blocks")
    rng = np.random.default_rng(RNG_SEED)
    by_policy = {}
    for policy, table in tables.items():
        mean, low, high = _interval(table.mean(axis=1), rng)
        by_policy[policy] = {"mean": mean, "ci95": [low, high]}
    comparisons = []
    for candidate, baseline in COMPARISONS:
        if candidate not in tables or baseline not in tables:
            continue
        cells = tables[candidate] - tables[baseline]
        mean, low, high = _interval(cells.mean(axis=1), rng)
        flat = cells.to_numpy().ravel()
        comparisons.append(
            {
                "candidate": candidate,
                "baseline": baseline,
                "mean_delta": mean,
                "ci95": [low, high],
                "better_runs": int((flat > 1e-12).sum()),
                "equal_runs": int((np.abs(flat) <= 1e-12).sum()),
                "worse_runs": int((flat < -1e-12).sum()),
                "conclusion": "higher" if low > 0 else "lower" if high < 0 else "inconclusive",
            }
        )
    first = tables[policies[0]]
    return {
        "metric": metric,
        "method": "paired percentile bootstrap over seed blocks",
        "draws": DRAWS,
        "rng_seed": RNG_SEED,
        "seed_blocks": int(len(first.index)),
        "cells_per_block": int(first.shape[1]),
        "by_policy": by_policy,
        "comparisons": comparisons,
    }


def version_effects(before, after, metrics=("delivery_ratio", "route_changes", "p95_latency_s")):
    """Paired after-minus-before effects per policy for two runs of the same workloads."""
    rng = np.random.default_rng(RNG_SEED)
    effects = {}
    for policy in sorted(set(before.policy) & set(after.policy)):
        effects[policy] = {}
        for metric in metrics:
            old, new = _blocks(before, policy, metric), _blocks(after, policy, metric)
            if not (old.index.equals(new.index) and old.columns.equals(new.columns)):
                raise ValueError("Versions do not cover the same seed blocks")
            mean, low, high = _interval((new - old).mean(axis=1), rng)
            effects[policy][metric] = {
                "before": float(old.to_numpy().mean()),
                "after": float(new.to_numpy().mean()),
                "mean_delta": mean,
                "ci95": [low, high],
            }
    return effects


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = paired_statistics(pd.read_csv(args.summary))
    atomic_json(result, Path(args.output))
    print(json.dumps(result["comparisons"], indent=2))


if __name__ == "__main__":
    main()
