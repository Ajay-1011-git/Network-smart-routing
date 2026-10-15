"""Publish compact evidence and human-readable reports from audited runs."""

import json
import shutil
from pathlib import Path

import pandas as pd

from smartroute.experiments.audit import audit
from smartroute.intelligence.model_io import file_hash, load_model
from smartroute.serialization import atomic_json


def main():
    root = Path("artifacts/final-benchmark")
    evidence = Path("docs/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    report = audit(root / "manifest.json")
    manifest = json.loads((root / "manifest.json").read_text())
    _, model = load_model("models/selected")
    summary = pd.read_csv(root / "summary.csv")
    paired = pd.read_csv(root / "paired_deltas.csv")
    accuracy = [
        {
            "topology": run["topology"],
            "scenario": run["scenario"],
            "seed": run["seed"],
            "policy": run["policy"],
            "family_id": run["family_id"],
            **flow,
        }
        for run in manifest["runs"]
        for flow in run["forecast_scores"]
    ]
    pd.DataFrame(accuracy).to_csv(root / "forecast_accuracy.csv", index=False)
    per_flow = [
        {
            "family_id": run["family_id"],
            "scenario": run["scenario"],
            "topology": run["topology"],
            "seed": run["seed"],
            "policy": run["policy"],
            **flow,
            "offered_normalized_delivery": flow["delivered"] / flow["generated"]
            if flow["generated"]
            else None,
        }
        for run in manifest["runs"]
        for flow in run["flow_metrics"]
    ]
    pd.DataFrame(per_flow).to_csv(root / "per_flow.csv", index=False)
    for file in (
        "report.json",
        "summary.csv",
        "aggregate.csv",
        "paired_deltas.csv",
        "forecast_accuracy.csv",
        "per_flow.csv",
    ):
        shutil.copyfile(root / file, evidence / file)
    for suite in ("validation-ablation", "stress", "smoke"):
        audit(Path("artifacts") / suite / "manifest.json")
        for file in ("report.json", "summary.csv"):
            shutil.copyfile(Path("artifacts") / suite / file, evidence / f"{suite}-{file}")
    atomic_json(
        {
            **report,
            "experiment_version": model["experiment_version"],
            "manifest_path": "artifacts/final-benchmark/manifest.json",
            "manifest_sha256": file_hash(root / "manifest.json"),
            "model_sha256": model["model_sha256"],
            "source_hash": model["source_hash"],
            "freeze_sha256": file_hash("models/selected/freeze.json"),
            "environment": manifest["environment"],
            "benchmark_duration_s": manifest["duration_s"],
            "split_hashes": model["split_hashes"],
        },
        evidence / "benchmark-audit.json",
    )

    lines = [
        f"# Measured results — experiment {model['experiment_version']}",
        "",
        f"The complete sealed matrix passed audit: **{report['runs']} runs**, {report['families']} workload families, zero failures.",
        "Seven scenario families × two topologies × five seeds × five policies. Every paired workload shares its packet/event trace hash.",
        "",
        "## Overall outcomes",
        "",
        "These are unweighted means of 70 run-level observations per policy, not a pooled packet delivery ratio.",
        "",
        "| Policy | Delivery | Cohort goodput (Mbit/s) | Mean latency (ms) | P95 (ms) | Changes/run | Decision time (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, group in summary.groupby("policy"):
        avg = group.mean(numeric_only=True)
        lines.append(
            f"| {name} | {avg.delivery_ratio:.2%} | {avg.throughput_bps / 1e6:.3f} | {avg.mean_latency_s * 1000:.2f} | {avg.p95_latency_s * 1000:.2f} | {avg.route_changes:.2f} | {avg.decision_runtime_ms:.4f} |"
        )
    lines += [
        "",
        "## Scenario-level delivery",
        "",
        "Mean ± sample SD across ten topology/seed run units per scenario/policy. There are five seeds per topology.",
        "",
        "| Scenario | Static | Reactive / persistence | Trend | Learned |",
        "|---|---:|---:|---:|---:|",
    ]
    for scenario, group in summary.groupby("scenario"):
        cells = []
        for policy in ("static", "reactive", "predictive-trend", "predictive-learned"):
            values = group.loc[group.policy == policy, "delivery_ratio"]
            cells.append(f"{values.mean():.2%} ± {values.std():.2%}")
        lines.append(f"| {scenario} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Paired differences from reactive",
        "",
        "Delivery deltas below use matching topology/scenario/seed runs. SD is across run units, not packets.",
        "",
        "| Policy | Mean delivery delta (percentage points) | SD (points) | Better / equal / worse runs |",
        "|---|---:|---:|---:|",
    ]
    for policy, group in paired.groupby("policy"):
        delta = group.delta_delivery_ratio
        lines.append(
            f"| {policy} | {100 * delta.mean():+.3f} | {100 * delta.std():.3f} | {(delta > 1e-12).sum()} / {(delta.abs() <= 1e-12).sum()} / {(delta < -1e-12).sum()} |"
        )
    lines += [
        "",
        "Persistence and reactive match by design; their packet outcomes are also checked in tests.",
        "The learned predictor improves aggregate delivery over reactive here, while trend performs better overall. A lower forecast error does not establish a better routing controller.",
        "Delivered-only latency can fall when delayed packets drop; read it with delivery, drop and pending rates. All final test runs have zero pending packets.",
        "",
        "## Forecast accuracy",
        "",
        "Validation uses complete one-second future means, after ten completed history windows. Units are bit/s.",
        "",
        "| Validation predictor | MAE | RMSE |",
        "|---|---:|---:|",
    ]
    for name, values in model["validation_scores"].items():
        lines.append(f"| {name} | {values['mae_bps']:.1f} | {values['rmse_bps']:.1f} |")
    acc = pd.DataFrame(accuracy)
    lines += [
        "",
        "Test accuracy below includes the online predictor's explicit support fallback. It excludes warm-up/tail windows.",
        "",
        "| Online predictor | Mean per-flow/workload MAE (bit/s) | Mean per-flow/workload RMSE (bit/s) |",
        "|---|---:|---:|",
    ]
    for policy, group in acc.groupby("policy"):
        lines.append(f"| {policy} | {group.mae_bps.mean():.1f} | {group.rmse_bps.mean():.1f} |")
    lines += [
        "",
        "## Stability and unseen-traffic stress",
        "",
        "The validation-only ablation has 32 runs: two scenarios × two topologies × one seed × four dynamic policies × two guard settings. Scorer alpha and candidate search remain identical.",
        "",
        "| Validation setting | Mean delivery | Mean changes/run |",
        "|---|---:|---:|",
    ]
    ablation = pd.read_csv("artifacts/validation-ablation/summary.csv")
    for variant, group in ablation.groupby("variant"):
        lines.append(
            f"| {variant} | {group.delivery_ratio.mean():.2%} | {group.route_changes.mean():.2f} |"
        )
    lines += [
        "",
        "Removing cooldown/hysteresis trades extra switching for delivery in these cases; this is a stability tradeoff, not proof the chosen guards dominate.",
        "The separate 20-run stress suite uses an unseen abrupt-spike amplitude and duty cycle. It is excluded from the headline matrix.",
        "",
        "| Stress policy | Mean delivery |",
        "|---|---:|",
    ]
    stress = pd.read_csv("artifacts/stress/summary.csv")
    for policy, group in stress.groupby("policy"):
        lines.append(f"| {policy} | {group.delivery_ratio.mean():.2%} |")
    lines += [
        "",
        "## Reproducibility and limits",
        "",
        f"Benchmark wall time: {manifest['duration_s']:.2f} seconds on {manifest['environment']['platform']} / Python {manifest['environment']['python']}. Timing is observational and hardware-specific.",
        f"Model SHA256: `{model['model_sha256']}`.",
        f"Full manifest SHA256: `{file_hash(root / 'manifest.json')}`.",
        f"Model/scorer/splits were frozen before sealed evaluation. Experiment {model['experiment_version']} regenerates the source-verified matrix for the React/live API addition. Earlier boundary corrections are documented in DECISIONS.md; no hyperparameters changed after test inspection.",
        "Reactive remains the preselected dashboard default. Five seeds are a small local-study budget; these results do not establish generality, causality outside this simulator, or statistical significance.",
        "Per-flow/workload forecast errors, offered-normalized delivery, null-preserving aggregates, seed deltas, fairness, drop/pending counts and timings are in docs/evidence/. Full packet ledgers remain in artifacts/final-benchmark/runs/.",
        "Reproduce with the README commands. Run failures are retained and block a complete audit; no failed run is filled with zero metrics.",
    ]
    Path("docs/RESULTS.md").write_text("\n\n".join([]) + "\n".join(lines) + "\n")
    model_lines = [
        "# Model card",
        "",
        f"Experiment version: {model['experiment_version']}",
        "",
        f"Model: {model['estimator']}, Ridge alpha={model['alpha']}. Artifact size: {Path('models/selected/model.joblib').stat().st_size} bytes.",
        "",
        f"Training: {model['train_rows']} rows / 140 workload families. Validation: {model['validation_rows']} rows / 42 families. Test: 70 disjoint families.",
        "",
        "Purpose: estimate each flow's mean source offered rate over the next second from ten completed 0.2-second observations. Rates are open-loop and independent of routing.",
        "",
        "Features: "
        + ", ".join(model["feature_names"])
        + ". Feature values use Mbit/s; final forecasts use bit/s.",
        "",
        "StandardScaler fits on train only. Three predeclared Ridge regularization strengths are compared on validation MAE. The smallest MAE chooses the model, without opening sealed test results. Shared route-scorer defaults are not tuned.",
        "",
        "The zero-duration initial snapshot is excluded from history. Warm-up uses persistence. Unsupported features and nonfinite/negative/unsupported learned outputs explicitly fall back to current observed demand, with a logged reason. Support bounds use train/validation extrema plus a margin; they are not uncertainty estimates.",
        "",
        "Flow/node IDs, scenario names, seeds, traffic segments, future events and future packets never enter the feature vector. Offline labels are complete future-horizon source packet counts and are unavailable before horizon end. All flows/policy traces in a workload family share one split.",
        "",
        "Limitations: sudden unannounced spikes cannot be anticipated reliably. Ridge can underfit periodic bursts; a forecast winner can lose in the routing experiment. The small catalog and seed budget limit generalization. See RESULTS.md and DECISIONS.md.",
        "",
        f"Model SHA256: `{model['model_sha256']}`. Source SHA256: `{model['source_hash']}`.",
        "",
        "Metadata includes schema, ordered feature names/hash, dependency versions, split hashes/manifests, support bounds, validation scores and the exact scorer. A fresh process reloads the verified artifact. Joblib files are executable: only project-generated trusted model/artifact directories are accepted, and the UI never accepts uploaded models.",
        "",
        "The model is included at models/selected/model.joblib. Regenerate with `python -m smartroute.intelligence.train --output models/selected`, then rerun all affected suites. See README for the full sequence.",
    ]
    Path("docs/MODEL_CARD.md").write_text("\n".join(model_lines) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
