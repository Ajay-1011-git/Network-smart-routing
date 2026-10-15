from dataclasses import replace

import pytest

from smartroute.baselines import ReactivePolicy
from smartroute.baselines.scoring import choose_routes
from smartroute.contracts import (
    FlowObservation,
    FlowSpec,
    LinkObservation,
    PacketOutcome,
    RunConfig,
    Snapshot,
)
from smartroute.engine.metrics import compute_metrics


def snapshot():
    links = tuple(
        LinkObservation(id_, a, b, True, 1e6, 0.001, 16000, 0, 0, 0, 0, 0, 0.0)
        for id_, a, b in [("sa", "s", "a"), ("at", "a", "t"), ("sb", "s", "b"), ("bt", "b", "t")]
    )
    flows = (
        FlowObservation("a", "s", "t", 1000, 800000.0, ("sa", "at"), None),
        FlowObservation("b", "s", "t", 1000, 800000.0, ("sa", "at"), None),
    )
    return Snapshot("1.0", 2.0, 0.2, 1.0, links, flows)


def test_reservations_spread_competing_flows():
    snap = snapshot()
    choices = choose_routes(snap, {"a": 800000.0, "b": 800000.0})
    assert choices[0].link_ids != choices[1].link_ids
    assert all(c.projected_peak_load == pytest.approx(0.8) for c in choices)
    assert ReactivePolicy().decide(snap).routes == choices


def test_cooldown_and_failure_bypass():
    snap = snapshot()
    snap = replace(snap, flows=tuple(replace(f, last_switch_s=1.8) for f in snap.flows))
    choices = choose_routes(snap, {"a": 800000.0, "b": 800000.0})
    assert all(c.link_ids == ("sa", "at") for c in choices)
    broken = replace(
        snap, links=tuple(replace(e, up=False) if e.id == "sa" else e for e in snap.links)
    )
    assert all(
        c.reason == "forced_repair" and c.link_ids == ("sb", "bt")
        for c in choose_routes(broken, {"a": 800000.0, "b": 800000.0})
    )


def test_fairness_keeps_active_zero_delivery_flow():
    config = RunConfig(
        "x",
        "x",
        0,
        ("s", "t"),
        (),
        (FlowSpec("a", "s", "t", 10), FlowSpec("b", "s", "t", 10)),
        (),
        (),
        warmup_s=0.0,
        measure_s=1.0,
        drain_s=1.0,
    )
    packets = (
        PacketOutcome(0, "a", 0.0, 10, "delivered", 0.1, None, 1),
        PacketOutcome(1, "b", 0.0, 10, "dropped", 0.0, "no_route", 1),
    )
    metrics, flows = compute_metrics(config, packets)
    assert metrics.fairness == 0.5
    assert metrics.delivery_ratio == 0.5 and metrics.throughput_bps == 80.0
    assert metrics.mean_latency_s == 0.1 and flows[1].mean_latency_s is None
