import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from smartroute.engine.sdk import SimulationEngine
from smartroute.engine.topology import catalog_config
from smartroute.intelligence.model_io import load_model
from smartroute.intelligence.policy import PredictivePolicy


def test_trained_model_and_support_fallback():
    estimator, metadata = load_model("models/selected")
    assert metadata["train_rows"] > 1000 and metadata["validation_rows"] > 1000
    assert np.isfinite(estimator.predict(np.zeros((1, 22)))).all()
    engine, config = SimulationEngine(), catalog_config(scenario="ramp")
    result = engine.run(config, engine.make_workload(config), PredictivePolicy("learned"))
    forecasts = [f for d in result.decisions for f in d.decision.forecasts]
    assert any(f.status == "model" for f in forecasts)
    assert all(np.isfinite(f.rate_bps) and f.rate_bps >= 0 for f in forecasts)
    policy = PredictivePolicy("learned")
    policy.metadata["support_min"] = [1e9] * 22
    policy.metadata["support_max"] = [1e9] * 22
    fallback = engine.run(config, engine.make_workload(config), policy)
    assert any(
        f.status == "fallback" and "support" in f.reason
        for d in fallback.decisions
        for f in d.decision.forecasts
    )


def test_model_metadata_tampering_rejected():
    target = Path("artifacts/test-model-tampering")
    shutil.copytree("models/selected", target, dirs_exist_ok=True)
    meta_path = target / "metadata.json"
    metadata = json.loads(meta_path.read_text())
    metadata["feature_hash"] = "tampered"
    meta_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="mismatch"):
        load_model(target)


def test_future_source_mutation_does_not_change_earlier_predictions():
    from dataclasses import replace

    config = catalog_config(scenario="spike")
    changed = replace(
        config,
        traffic=tuple(
            replace(s, start_bps=s.start_bps * 1.5, end_bps=s.end_bps * 1.5)
            if s.start_s >= 4
            else s
            for s in config.traffic
        ),
    )
    engine = SimulationEngine()
    before, after = [
        engine.run(c, engine.make_workload(c), PredictivePolicy("learned"))
        for c in (config, changed)
    ]
    assert [d.decision for d in before.decisions if d.time_s < 4] == [
        d.decision for d in after.decisions if d.time_s < 4
    ]


def test_invalid_model_output_explicit_fallback():
    class InvalidEstimator:
        def predict(self, values):
            return [float("nan")]

    policy = PredictivePolicy("learned")
    policy.estimator = InvalidEstimator()
    engine, config = SimulationEngine(), catalog_config()
    result = engine.run(config, engine.make_workload(config), policy)
    assert any(
        f.status == "fallback" and "invalid" in f.reason
        for d in result.decisions
        for f in d.decision.forecasts
    )


def test_learned_model_rejects_different_target_horizon():
    from dataclasses import replace

    engine, config = SimulationEngine(), catalog_config()
    snapshot = engine.run(config, engine.make_workload(config), PredictivePolicy()).snapshots[0]
    with pytest.raises(ValueError, match="trained observation interval and horizon"):
        PredictivePolicy("learned").decide(replace(snapshot, horizon_s=2.0))
