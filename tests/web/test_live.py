from copy import deepcopy

import pytest

from smartroute.engine.errors import ConfigurationError
from smartroute.web.live import LiveSession


def graph():
    return {
        "nodes": [
            {"id": id_, "kind": "router", "label": id_, "position": {"x": 0, "y": 0}}
            for id_ in ("s", "a", "b", "t")
        ],
        "connections": [
            {
                "id": id_,
                "source": a,
                "target": b,
                "capacity_mbps": cap,
                "latency_ms": latency,
                "buffer_bytes": 64000,
                "up": True,
            }
            for id_, a, b, cap, latency in [
                ("sa", "s", "a", 1, 2),
                ("at", "a", "t", 1, 2),
                ("sb", "s", "b", 2.5, 12),
                ("bt", "b", "t", 2.5, 12),
            ]
        ],
        "flows": [{"id": "f", "source": "s", "target": "t", "rate_mbps": 0.35}],
        "policy": "reactive",
    }


def step_many(session, count):
    for _ in range(count):
        result = session.step()
    return result


def test_traffic_change_reroutes_existing_session_and_preserves_ledger():
    session = LiveSession(graph())
    low = step_many(session, 20)
    assert low["decision"]["routes"][0]["link_ids"] == ("sa:fwd", "at:fwd")
    old = deepcopy(session.outcomes)
    session.step({"rates": {"f": 1.8}})
    high = step_many(session, 20)
    assert high["decision"]["routes"][0]["link_ids"] == ("sb:fwd", "bt:fwd")
    assert session.env.now > low["time_s"]
    for id_, packet in old.items():
        assert session.outcomes[id_].route_version == packet.route_version
        if packet.status != "pending":
            assert session.outcomes[id_] == packet
    assert high["metrics"]["route_changes"] == 1
    metrics = high["metrics"]
    assert metrics["generated"] == metrics["delivered"] + metrics["dropped"] + metrics["pending"]


def test_link_failure_repairs_route_at_the_next_tick_without_cooldown():
    session = LiveSession(graph())
    step_many(session, 3)
    result = session.step({"connections": {"sa": {"up": False}}})
    assert result["decision"]["routes"][0]["reason"] == "forced_repair"
    assert result["metrics"]["forced_route_changes"] == 1
    session.step({"connections": {"sa": {"capacity_mbps": 0.5}}})
    assert not session.links["sa:fwd"].up


def test_capacity_changes_do_not_reset_in_service_packets():
    session = LiveSession(graph())
    session.step({"rates": {"f": 2.0}})
    old_generated = len(session.outcomes)
    before = session.env.now
    result = session.step({"connections": {"sa": {"capacity_mbps": 0.1}}})
    assert session.env.now == pytest.approx(before + 0.2)
    assert len(session.outcomes) > old_generated
    assert session.links["sa:fwd"].port.rate == 100000
    assert result["metrics"]["generated"] == len(session.outcomes)


def test_disconnected_traffic_and_exact_boundary_generation():
    data = graph()
    data["connections"] = []
    data["flows"][0]["rate_mbps"] = 0.04
    session = LiveSession(data)
    session.credits["f"] = 0
    assert session.step()["metrics"]["generated"] == 0
    result = session.step()
    assert result["metrics"]["generated"] == result["metrics"]["dropped"] == 1
    assert session.outcomes[0].generated_s == 0.2
    assert session.outcomes[0].drop_reason == "no_route"


def test_validation_is_atomic_and_export_retains_original_network():
    data = graph()
    original = deepcopy(data)
    session = LiveSession(data)
    with pytest.raises(ConfigurationError):
        session.apply({"rates": {"f": 1.0}, "connections": {"missing": {"capacity_mbps": 1.0}}})
    assert session.rates["f"] == 350000
    session.step({"connections": {"sa": {"capacity_mbps": 2.0}}})
    exported = session.export()
    assert exported["network"] == original and data == original
    assert exported["edits"][0]["connections"]["sa"]["capacity_mbps"] == 2.0
    assert exported["packets"]


@pytest.mark.parametrize("value", [True, float("nan"), -1, "100", None])
def test_bad_capacity_is_rejected(value):
    data = graph()
    data["connections"][0]["capacity_mbps"] = value
    with pytest.raises(ConfigurationError):
        LiveSession(data)


def test_transmissions_have_real_packet_ids_and_direction():
    session = LiveSession(graph())
    result = step_many(session, 5)
    assert result["transmissions"]
    for event in result["transmissions"]:
        assert event["packet_id"] in session.outcomes
        assert event["link_id"] in session.links
        assert event["time_s"] < result["time_s"]
        assert event["source"] == session.links[event["link_id"]].spec.src
