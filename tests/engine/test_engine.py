from dataclasses import asdict, replace

import pytest

from smartroute.baselines import ReactivePolicy, StaticPolicy
from smartroute.contracts import (
    Decision,
    FlowSpec,
    LinkEvent,
    LinkSpec,
    RateSegment,
    RouteChoice,
    RunConfig,
    TracePacket,
    Workload,
)
from smartroute.engine.errors import ConfigurationError, PolicyError
from smartroute.engine.sdk import SimulationEngine
from smartroute.engine.topology import SCENARIOS, TOPOLOGIES, catalog_config, validate_config
from smartroute.engine.workload import trace_digest
from smartroute.serialization import (
    load_config,
    load_result,
    load_workload,
    save_config,
    save_result,
    save_workload,
)


def simple(*, buffer=100, capacity=80.0, propagation=0.01, drain=3.0, events=(), measure=1.0):
    return RunConfig(
        "test",
        "analytic",
        0,
        ("s", "t"),
        (LinkSpec("st", "s", "t", capacity, propagation, buffer),),
        (FlowSpec("f", "s", "t", 10),),
        (),
        tuple(events),
        warmup_s=0.0,
        measure_s=measure,
        drain_s=drain,
        interval_s=0.2,
    )


def run_packets(config, times, policy=None):
    packets = tuple(TracePacket(i, "f", t, 10) for i, t in enumerate(times))
    workload = Workload("1.0", trace_digest(packets, config.events), packets)
    return SimulationEngine().run(config, workload, policy or StaticPolicy())


def test_analytic_fifo_and_busy():
    result = run_packets(simple(buffer=20), [0.0, 0.0, 0.0])
    assert [p.status for p in result.packets] == ["delivered", "delivered", "dropped"]
    assert [p.terminal_s for p in result.packets[:2]] == pytest.approx([1.01, 2.01])
    assert result.metrics.throughput_bps == 160.0
    assert result.snapshots[1].links[0].resident_bytes == 20
    assert result.snapshots[1].links[0].busy_s == pytest.approx(0.2)
    assert result.snapshots[1].links[0].served_bits == 0


def test_zero_buffer_pending_and_no_traffic():
    assert run_packets(simple(buffer=0), [0.0]).packets[0].drop_reason == "buffer_overflow"
    pending = run_packets(simple(capacity=8.0, drain=0), [0.0])
    assert pending.metrics.pending == 1 and pending.metrics.mean_latency_s is None
    empty = run_packets(simple(), [])
    assert empty.metrics.fairness is None and empty.metrics.delivery_ratio is None


def test_capacity_captured_at_service_start():
    config = simple(events=(LinkEvent(0.4, "st", "capacity", 160.0),))
    result = run_packets(config, [0.0, 0.1])
    assert [p.terminal_s for p in result.packets] == pytest.approx([1.01, 1.51])


def test_down_queue_and_recovery():
    config = simple(events=(LinkEvent(0.4, "st", "down"),))
    result = run_packets(config, [0.0, 0.1, 0.6])
    assert [p.drop_reason for p in result.packets] == ["link_down", "link_down", "no_route"]
    recovering = replace(config, events=config.events + (LinkEvent(0.8, "st", "up"),))
    assert run_packets(recovering, [0.0]).packets[0].status == "delivered"


def test_in_wire_survives_failure():
    result = run_packets(
        simple(capacity=8000.0, propagation=1.0, events=(LinkEvent(0.2, "st", "down"),)), [0.0]
    )
    assert result.packets[0].terminal_s == pytest.approx(1.01)


def test_cutoff_excludes_tied_completion():
    result = run_packets(simple(capacity=80.0, propagation=0.0, drain=0.0), [0.0])
    assert result.packets[0].status == "pending"


def test_event_before_boundary_arrival():
    result = run_packets(simple(events=(LinkEvent(0.2, "st", "down"),)), [0.2])
    assert result.packets[0].drop_reason == "no_route"


def test_decimal_tick_does_not_drift_past_boundary_arrival():
    result = run_packets(simple(events=(LinkEvent(0.6, "st", "down"),)), [0.6])
    assert result.packets[0].drop_reason == "no_route"


def test_policy_is_snapshot_only_and_invalid_route_rejected():
    class Bad:
        name = "bad"

        def reset(self):
            pass

        def decide(self, snapshot):
            assert not hasattr(snapshot, "traffic") and not hasattr(snapshot, "events")
            return Decision((RouteChoice("f", (), "bad", None, None, None),), ())

    with pytest.raises(PolicyError):
        run_packets(simple(), [], Bad())


def test_roundtrips_and_determinism(tmp_path):
    config = catalog_config()
    engine = SimulationEngine()
    workload = engine.make_workload(config)
    assert engine.make_workload(config) == workload
    assert engine.make_workload(replace(config, seed=1)) != workload
    result = engine.run(config, workload, ReactivePolicy())
    other = engine.run(config, workload, ReactivePolicy())
    a, b = asdict(result), asdict(other)
    for record in a["decisions"] + b["decisions"]:
        record.pop("runtime_ms")
    assert a == b
    for name, obj, save, load in [
        ("config", config, save_config, load_config),
        ("workload", workload, save_workload, load_workload),
        ("result", result, save_result, load_result),
    ]:
        path = tmp_path / f"{name}.json"
        save(obj, path)
        assert load(path) == obj


@pytest.mark.parametrize("topology", TOPOLOGIES)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_catalog_matrix(topology, scenario):
    config = catalog_config(topology, scenario)
    engine = SimulationEngine()
    workload = engine.make_workload(config)
    for policy in (StaticPolicy(), ReactivePolicy()):
        result = engine.run(config, workload, policy)
        m = result.metrics
        assert m.generated == m.delivered + m.dropped + m.pending
        assert len(result.packets) == len(workload.packets)
        assert all(
            0 <= e.busy_s <= config.interval_s + 1e-8 for s in result.snapshots for e in s.links
        )


def test_validation_and_trace_rejection():
    with pytest.raises(ConfigurationError):
        validate_config(simple(buffer=True))
    with pytest.raises(ConfigurationError):
        validate_config(simple(events=(LinkEvent(0.3, "st", "down"),)))
    config = simple()
    with pytest.raises(ConfigurationError):
        SimulationEngine().run(config, Workload("1.0", "0" * 64, ()), StaticPolicy())


def test_integral_packet_quantization():
    config = replace(
        simple(measure=2.0), traffic=(RateSegment("f", 0.0, 2.0, "linear", 80.0, 160.0),)
    )
    workload = SimulationEngine().make_workload(config)
    assert abs(len(workload.packets) * 80 - 240) <= 80
