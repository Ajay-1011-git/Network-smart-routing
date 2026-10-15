"""Generate summaries from real successful runs, retaining missing/null values."""

import pandas as pd

from smartroute.serialization import atomic_json


def write_report(manifest, output):
    rows = [
        {
            **{
                key: r[key]
                for key in ("family_id", "scenario", "topology", "seed", "policy", "variant")
            },
            **r["metrics"],
            "decision_runtime_ms": r["decision_runtime_ms"],
            "fallback_fraction": r["fallback_fraction"],
        }
        for r in manifest["runs"]
        if r["status"] == "complete"
    ]
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "summary.csv", index=False)
    if frame.empty:
        return
    metrics = [
        "delivery_ratio",
        "mean_latency_s",
        "p95_latency_s",
        "throughput_bps",
        "drop_ratio",
        "pending",
        "fairness",
        "route_changes",
        "forced_route_changes",
        "decision_runtime_ms",
        "fallback_fraction",
    ]
    aggregate = frame.groupby(["scenario", "policy", "variant"])[metrics].agg(
        ["mean", "std", "count"]
    )
    aggregate.to_csv(output / "aggregate.csv")
    paired = []
    for (scenario, topology, seed, variant), group in frame.groupby(
        ["scenario", "topology", "seed", "variant"]
    ):
        baseline = group[group.policy == "reactive"]
        if len(baseline) != 1:
            continue
        base = baseline.iloc[0]
        for _, row in group.iterrows():
            paired.append(
                {
                    "scenario": scenario,
                    "topology": topology,
                    "seed": int(seed),
                    "policy": row.policy,
                    "variant": variant,
                    **{
                        f"delta_{key}": None
                        if pd.isna(row[key]) or pd.isna(base[key])
                        else float(row[key] - base[key])
                        for key in metrics
                        if key != "fallback_fraction"
                    },
                }
            )
    pd.DataFrame(paired).to_csv(output / "paired_deltas.csv", index=False)
    compact = {
        "suite": manifest["suite"],
        "status": manifest["status"],
        "expected_runs": manifest["expected_runs"],
        "completed_runs": len(rows),
        "failed_runs": sum(r["status"] != "complete" for r in manifest["runs"]),
        "by_policy": {
            policy: {
                metric: None if pd.isna(value) else float(value)
                for metric, value in group[metrics].mean().items()
            }
            for policy, group in frame.groupby("policy")
        },
    }
    atomic_json(compact, output / "report.json")
