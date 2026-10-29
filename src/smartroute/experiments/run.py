"""Paired runs over a frozen workload matrix, with explicit failure manifests."""

import argparse
import json
import platform
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import numpy as np

from smartroute.cli import POLICIES, make_policy
from smartroute.engine.sdk import SimulationEngine
from smartroute.intelligence.dataset import rows_for, split_manifest, suite_configs
from smartroute.intelligence.model_io import dependencies, file_hash, load_model, source_hash
from smartroute.intelligence.train import error_scores
from smartroute.serialization import atomic_json, digest, save_result


def run_suite(suite, model, output):
    output = Path(output).resolve()
    _, metadata = load_model(model)
    freeze = json.loads((Path(model) / "freeze.json").read_text())
    if freeze["model_sha256"] != metadata["model_sha256"] or freeze["source_hash"] != source_hash():
        raise ValueError("Model/freeze mismatch")
    if suite == "full":
        spec = json.loads(Path("experiment_configs/test.json").read_text())
    elif suite == "extended-test":
        # Fresh held-out seeds: disjoint from train/validation/test and never used for selection.
        spec = json.loads(Path("experiment_configs/extended-test.json").read_text())
    elif suite == "smoke":
        spec = json.loads(Path("experiment_configs/smoke.json").read_text())
    elif suite == "stress":
        spec = {"split": "stress", "seeds": [205, 206], "scenarios": ["spike"], "stress": True}
    else:
        spec = {"split": "validation", "seeds": [100], "scenarios": ["ramp", "competing"]}
    split = split_manifest(spec)
    if suite == "full" and digest(split) != metadata["split_hashes"][2]:
        raise ValueError("Sealed test specification changed")
    if suite == "extended-test":
        used = {f for m in metadata["split_manifests"] for f in m["families"]}
        if used & set(split["families"]):
            raise ValueError("Extended test overlaps model train/validation/test families")
    configurations = list(suite_configs(spec))
    policies = POLICIES if suite != "validation-ablation" else POLICIES[1:]
    variants = ("default", "no-hysteresis") if suite == "validation-ablation" else ("default",)
    expected = len(configurations) * len(policies) * len(variants)
    manifest = {
        "schema_version": "1.0",
        "experiment_version": metadata["experiment_version"],
        "suite": suite,
        "status": "incomplete",
        "expected_runs": expected,
        "spec": spec,
        "model_sha256": metadata["model_sha256"],
        "source_hash": source_hash(),
        "freeze_sha256": file_hash(Path(model) / "freeze.json"),
        "model_path": str(Path(model).resolve()),
        "split_hashes": metadata["split_hashes"],
        "scorer": metadata["scorer"],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "dependencies": dependencies(),
        },
        "expected_families": sorted(split["families"]),
        "runs": [],
    }
    engine = SimulationEngine()
    begun = perf_counter()
    for config in configurations:
        workload = engine.make_workload(config)
        family = digest(config)
        for variant in variants:
            for policy_name in policies:
                key = f"{config.topology_id}-{config.scenario_id}-{config.seed}-{policy_name}-{variant}"
                file = Path("runs") / f"{key}.json"
                entry = {
                    "key": key,
                    "family_id": family,
                    "topology": config.topology_id,
                    "scenario": config.scenario_id,
                    "seed": config.seed,
                    "policy": policy_name,
                    "variant": variant,
                    "config_sha256": family,
                    "trace_sha256": workload.trace_sha256,
                    "model_sha256": metadata["model_sha256"],
                    "file": str(file),
                }
                start = perf_counter()
                try:
                    scorer = (
                        metadata["scorer"]
                        if variant == "default"
                        else {**metadata["scorer"], "improvement": 0.0, "cooldown_s": 0.0}
                    )
                    result = engine.run(config, workload, make_policy(policy_name, model, **scorer))
                    save_result(result, output / file)
                    forecasts = [f for d in result.decisions for f in d.decision.forecasts]
                    actuals = rows_for(result, workload, family, spec["split"])
                    forecast_lookup = {(f.issued_s, f.flow_id): f.rate_bps for f in forecasts}
                    forecast_scores = []
                    for flow in config.flows:
                        rows = [
                            r
                            for r in actuals
                            if r["flow_id"] == flow.id
                            and (r["issued_s"], flow.id) in forecast_lookup
                        ]
                        if rows:
                            forecast_scores.append(
                                {
                                    "flow_id": flow.id,
                                    "samples": len(rows),
                                    **error_scores(
                                        [r["target_bps"] for r in rows],
                                        [forecast_lookup[(r["issued_s"], flow.id)] for r in rows],
                                    ),
                                }
                            )
                    entry.update(
                        status="complete",
                        metrics=asdict(result.metrics),
                        flow_metrics=[asdict(f) for f in result.flow_metrics],
                        result_sha256=file_hash(output / file),
                        duration_s=perf_counter() - start,
                        decision_runtime_ms=float(
                            np.mean([d.runtime_ms for d in result.decisions])
                        ),
                        fallback_fraction=sum(f.status == "fallback" for f in forecasts)
                        / len(forecasts)
                        if forecasts
                        else None,
                        warmup_fraction=sum("warm-up" in f.reason for f in forecasts)
                        / len(forecasts)
                        if forecasts
                        else None,
                        forecast_scores=forecast_scores,
                        event_summary=[asdict(e) for e in config.events],
                    )
                except Exception as exc:
                    entry.update(status="failed", error=str(exc), error_type=type(exc).__name__)
                manifest["runs"].append(entry)
                if len(manifest["runs"]) % 10 == 0:
                    print(f"{suite}: {len(manifest['runs'])}/{expected} runs", flush=True)
            atomic_json(manifest, output / "manifest.json")
    failures = sum(run["status"] != "complete" for run in manifest["runs"])
    manifest.update(
        status="complete" if not failures and len(manifest["runs"]) == expected else "incomplete",
        completed_runs=expected - failures,
        failed_runs=failures,
        duration_s=perf_counter() - begun,
    )
    atomic_json(manifest, output / "manifest.json")
    from smartroute.experiments.report import write_report

    write_report(manifest, output)
    print(
        f"{manifest['status']}: {manifest['completed_runs']}/{expected}; failures={failures}; {manifest['duration_s']:.2f}s"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        choices=("smoke", "full", "extended-test", "stress", "validation-ablation"),
        default="smoke",
    )
    parser.add_argument("--model", default="models/selected")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    manifest = run_suite(args.suite, args.model, args.output)
    if manifest["status"] != "complete":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
