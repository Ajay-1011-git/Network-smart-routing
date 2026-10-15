"""Split families before creating windows; labels stay offline."""

import argparse
import json
from bisect import bisect_left
from dataclasses import replace
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd

from smartroute.baselines import ReactivePolicy, StaticPolicy
from smartroute.engine.sdk import SimulationEngine
from smartroute.engine.topology import SCENARIOS, TOPOLOGIES, catalog_config
from smartroute.intelligence.features import (
    FEATURE_HASH,
    FEATURE_NAMES,
    History,
    features,
    trend_rate,
)
from smartroute.serialization import atomic_json, digest


def suite_configs(spec):
    for topology in spec.get("topologies", TOPOLOGIES):
        for scenario in spec.get("scenarios", SCENARIOS):
            for seed in spec["seeds"]:
                config = catalog_config(
                    topology,
                    scenario,
                    seed,
                    0.7 + 0.15 * (seed % 5),
                    stress=spec.get("stress", False),
                )
                # Periods vary within a predeclared range, independent of split.
                yield replace(
                    config,
                    traffic=tuple(
                        replace(s, period_s=2.4 + 0.4 * (seed % 4)) if s.kind == "periodic" else s
                        for s in config.traffic
                    ),
                )


def split_manifest(spec):
    families = {
        digest(config): {
            "topology": config.topology_id,
            "scenario": config.scenario_id,
            "seed": config.seed,
            "config_sha256": digest(config),
        }
        for config in suite_configs(spec)
    }
    return {"split": spec["split"], "families": families, "spec_sha256": digest(spec)}


def rows_for(result, workload, family, split):
    config, history, rows = result.config, History(), []
    lookup = {}
    for flow in config.flows:
        packets = [p for p in workload.packets if p.flow_id == flow.id]
        lookup[flow.id] = (
            [p.generated_s for p in packets],
            np.cumsum([0] + [p.size_bytes * 8 for p in packets]),
        )
    stop = config.warmup_s + config.measure_s
    for snapshot in result.snapshots:
        history.update(snapshot)
        if snapshot.time_s + snapshot.horizon_s > stop + 1e-8:
            continue
        for flow in snapshot.flows:
            rates = history.rates[flow.id]
            vector = features(rates, snapshot.interval_s)
            if vector is None:
                continue
            times, prefix = lookup[flow.id]
            a = bisect_left(times, snapshot.time_s)
            b = bisect_left(times, snapshot.time_s + snapshot.horizon_s)
            target = float(prefix[b] - prefix[a]) / snapshot.horizon_s
            rows.append(
                {
                    **dict(zip(FEATURE_NAMES, vector)),
                    "target_bps": target,
                    "persistence_bps": flow.offered_bps,
                    "trend_bps": trend_rate(rates, snapshot.interval_s, snapshot.horizon_s),
                    "family_id": family,
                    "split": split,
                    "flow_id": flow.id,
                    "policy": result.policy_name,
                    "issued_s": snapshot.time_s,
                    "label_available_s": snapshot.time_s + snapshot.horizon_s,
                }
            )
    return rows


def build_dataset(spec, output):
    output = Path(output)
    manifest = split_manifest(spec)
    # Persist group membership before any windows are constructed.
    atomic_json(manifest, output / "split.json")
    engine, rows = SimulationEngine(), []
    begun = perf_counter()
    for index, config in enumerate(suite_configs(spec)):
        workload = engine.make_workload(config)
        for policy in (StaticPolicy(), ReactivePolicy()):
            result = engine.run(config, workload, policy)
            rows.extend(rows_for(result, workload, digest(config), spec["split"]))
        if index % 14 == 0:
            print(f"{spec['split']}: {index + 1} workloads, {len(rows)} rows", flush=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "rows.csv", index=False)
    atomic_json(
        {
            "feature_hash": FEATURE_HASH,
            "rows": len(frame),
            "families": len(manifest["families"]),
            "duration_s": perf_counter() - begun,
            "spec": spec,
            "rows_sha256": __import__("hashlib")
            .sha256((output / "rows.csv").read_bytes())
            .hexdigest(),
        },
        output / "metadata.json",
    )
    return frame, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_dataset(json.loads(Path(args.config).read_text()), args.output)


if __name__ == "__main__":
    main()
