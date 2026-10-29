"""Real SDK data, a predeclared Ridge grid, and a sealed test manifest."""

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from smartroute.baselines.scoring import DAMPING_DEFAULTS
from smartroute.intelligence.dataset import build_dataset, split_manifest
from smartroute.intelligence.features import FEATURE_NAMES
from smartroute.intelligence.model_io import save_model
from smartroute.serialization import atomic_json, digest


def error_scores(actual, predicted):
    error = np.asarray(predicted) - np.asarray(actual)
    return {"mae_bps": float(np.abs(error).mean()), "rmse_bps": float(np.sqrt((error**2).mean()))}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-config", default="experiment_configs/train.json")
    parser.add_argument("--validation-config", default="experiment_configs/validation.json")
    parser.add_argument("--output", default="models/selected")
    args = parser.parse_args(argv)
    train_spec = json.loads(Path(args.train_config).read_text())
    val_spec = json.loads(Path(args.validation_config).read_text())
    test_spec = json.loads(Path("experiment_configs/test.json").read_text())
    manifests = [split_manifest(spec) for spec in (train_spec, val_spec, test_spec)]
    groups = [set(m["families"]) for m in manifests]
    if any(groups[i] & groups[j] for i in range(3) for j in range(i)):
        raise ValueError("Train/validation/test workload family overlap")
    train, _ = build_dataset(train_spec, "artifacts/datasets/train")
    validation, _ = build_dataset(val_spec, "artifacts/datasets/validation")
    xtrain, ytrain = train[list(FEATURE_NAMES)].to_numpy(), train.target_bps.to_numpy() / 1_000_000
    xval, yval = validation[list(FEATURE_NAMES)].to_numpy(), validation.target_bps.to_numpy()
    scores = {
        name: error_scores(yval, validation[f"{name}_bps"]) for name in ("persistence", "trend")
    }
    candidates = []
    for alpha in (0.01, 1.0, 10.0):
        estimator = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        estimator.fit(xtrain, ytrain)
        predicted = np.maximum(0, estimator.predict(xval) * 1_000_000)
        score = error_scores(yval, predicted)
        candidates.append((score["mae_bps"], alpha, estimator, predicted))
        scores[f"ridge-{alpha}"] = score
    _, alpha, estimator, predictions = min(candidates, key=lambda item: item[:2])
    support = np.vstack((xtrain, xval))
    selected = {
        "estimator": "StandardScaler+Ridge",
        "alpha": alpha,
        "support_min": support.min(axis=0).tolist(),
        "support_max": support.max(axis=0).tolist(),
        "rate_ceiling_bps": float(max(train.target_bps.max(), validation.target_bps.max()) * 2),
        "scorer": {"alpha_s": 0.02, "improvement": 0.10, "cooldown_s": 1.0, "k": 4}
        | DAMPING_DEFAULTS,
        "scorer_selection": "Fixed shared-spec defaults; flap damping selected on validation only",
        "validation_scores": scores,
        "train_rows": len(train),
        "validation_rows": len(validation),
        "split_manifests": manifests,
        "split_hashes": [digest(m) for m in manifests],
        "feature_names": FEATURE_NAMES,
        "observation_interval_s": 0.2,
        "horizon_s": 1.0,
        "experiment_version": "1.4",
    }
    metadata = save_model(estimator, args.output, selected)
    freeze = {
        "model_sha256": metadata["model_sha256"],
        "source_hash": metadata["source_hash"],
        "split_hashes": metadata["split_hashes"],
        "scorer": metadata["scorer"],
        "test_manifest": manifests[2],
        "experiment_version": "1.4",
    }
    atomic_json(freeze, Path(args.output) / "freeze.json")
    grouped = []
    validation = validation.assign(learned_bps=predictions)
    for (family, flow), group in validation.groupby(["family_id", "flow_id"]):
        grouped.append(
            {
                "family_id": family,
                "flow_id": flow,
                **{
                    name: error_scores(group.target_bps, group[f"{name}_bps"])
                    for name in ("persistence", "trend", "learned")
                },
            }
        )
    atomic_json(grouped, Path(args.output) / "validation_by_workload.json")
    print(
        json.dumps(
            {
                "train_rows": len(train),
                "validation_rows": len(validation),
                "scores": scores,
                "alpha": alpha,
                "model_sha256": metadata["model_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
