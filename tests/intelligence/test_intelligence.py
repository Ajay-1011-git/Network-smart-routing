from dataclasses import replace

import numpy as np
import pytest

from smartroute.baselines import ReactivePolicy
from smartroute.engine.sdk import SimulationEngine
from smartroute.engine.topology import catalog_config
from smartroute.intelligence.dataset import rows_for, split_manifest
from smartroute.intelligence.features import History, features, trend_rate
from smartroute.intelligence.policy import PredictivePolicy


def test_features_causal_and_warmup():
    assert features([1.0] * 9, 0.2) is None
    history = list(np.arange(10) * 10000.0)
    before = features(history, 0.2)
    future = history + [99999999.0]
    assert np.array_equal(before, features(future[:10], 0.2))
    assert trend_rate([10000.0] * 10, 0.2, 1.0) == pytest.approx(10000.0)
    assert trend_rate(history, 0.2, 1.0) > history[-1]
    with pytest.raises(ValueError):
        features([float("nan")] * 10, 0.2)


def test_disjoint_groups_before_windowing():
    train = split_manifest({"split": "train", "seeds": [0]})
    val = split_manifest({"split": "validation", "seeds": [100]})
    assert not set(train["families"]) & set(val["families"])
    assert len(train["families"]) == 14


def test_online_batch_alignment_and_complete_labels():
    engine, config = SimulationEngine(), catalog_config()
    workload = engine.make_workload(config)
    result = engine.run(config, workload, ReactivePolicy())
    rows = rows_for(result, workload, "family", "train")
    assert min(row["issued_s"] for row in rows) == 2.0
    assert all(
        row["label_available_s"] <= 12.0 and row["label_available_s"] > row["issued_s"]
        for row in rows
    )
    history = History()
    for snap in result.snapshots:
        history.update(snap)
        for row in (r for r in rows if r["issued_s"] == snap.time_s):
            from smartroute.intelligence.features import FEATURE_NAMES

            assert np.allclose(
                [row[name] for name in FEATURE_NAMES], features(history.rates[row["flow_id"]], 0.2)
            )
    with pytest.raises(ValueError):
        history.update(result.snapshots[0])


def test_persistence_reactive_equivalence_and_reset():
    engine, config = SimulationEngine(), catalog_config()
    workload = engine.make_workload(config)
    policy = PredictivePolicy()
    a = engine.run(config, workload, ReactivePolicy())
    b = engine.run(config, workload, policy)
    c = engine.run(config, workload, policy)
    assert [d.decision.routes for d in a.decisions] == [d.decision.routes for d in b.decisions]
    assert b.packets == c.packets == a.packets
    assert b.decisions[0].decision.forecasts[0].status == "persistence"
    assert "warm-up" in b.decisions[0].decision.forecasts[0].reason


def test_schema_rejected_and_missing_model_visible():
    engine, config = SimulationEngine(), catalog_config()
    result = engine.run(config, engine.make_workload(config), ReactivePolicy())
    with pytest.raises(ValueError):
        PredictivePolicy().decide(replace(result.snapshots[0], schema_version="99"))
    with pytest.raises((ValueError, FileNotFoundError)):
        PredictivePolicy("learned", "/tmp/untrusted")
