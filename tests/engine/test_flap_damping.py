from dataclasses import replace

import pytest

from smartroute.baselines import ReactivePolicy
from smartroute.baselines.scoring import FlapDamper, choose_routes, split_scorer
from smartroute.contracts import FlowObservation, LinkObservation, Snapshot
from smartroute.engine.errors import PolicyError

ALPHA, BETA = ("sa", "at"), ("sb", "bt")


def snapshot(time_s, route, last_switch_s, rate=600000.0, alpha_queue=0, alpha_up=True):
    specs = [
        ("sa", "s", "a", 1e6, 0.002, alpha_queue, alpha_up),
        ("at", "a", "t", 1e6, 0.002, alpha_queue, alpha_up),
        ("sb", "s", "b", 2.5e6, 0.012, 0, True),
        ("bt", "b", "t", 2.5e6, 0.012, 0, True),
    ]
    links = tuple(
        LinkObservation(id_, a, b, up, cap, delay, 64000, queue, 0, 0, 0, 0, 0.0)
        for id_, a, b, cap, delay, queue, up in specs
    )
    flows = (FlowObservation("f", "s", "t", 1000, rate, route, last_switch_s),)
    return Snapshot("1.0", time_s, 0.2, 1.0, links, flows)


def test_reversal_to_a_left_path_waits_for_hold_down():
    damper = FlapDamper(hold_s=8.0, half_life_s=15.0, max_hold_s=16.0)
    # Own queue on Alpha makes Beta cheaper: an ordinary first switch is allowed.
    (leave,) = choose_routes(
        snapshot(1.0, ALPHA, None, alpha_queue=8000), {"f": 6e5}, damper=damper
    )
    assert leave.link_ids == BETA and leave.reason == "switch"
    # Alpha drains and looks cheaper again; returning is a reversal and is held down.
    (held,) = choose_routes(snapshot(2.0, BETA, 1.0), {"f": 6e5}, damper=damper)
    assert held.link_ids == BETA and held.reason == "flap_damping"
    (back,) = choose_routes(snapshot(9.0, BETA, 1.0), {"f": 6e5}, damper=damper)
    assert back.link_ids == ALPHA and back.reason == "switch"


def test_each_reversal_doubles_the_next_hold_down():
    damper = FlapDamper(hold_s=2.0, half_life_s=1000.0, max_hold_s=16.0)
    flow = snapshot(0, ALPHA, None).flows[0]
    damper.record(flow, BETA, 0.0)
    on_beta = replace(flow, route=BETA, last_switch_s=0.0)
    assert not damper.allows(on_beta, ALPHA, 1.9, 0.3) and damper.allows(on_beta, ALPHA, 2.0, 0.3)
    damper.record(on_beta, ALPHA, 2.0)
    on_alpha = replace(flow, last_switch_s=2.0)
    assert not damper.allows(on_alpha, BETA, 5.9, 0.6) and damper.allows(on_alpha, BETA, 6.0, 0.6)


def test_overloaded_current_path_is_never_held():
    damper = FlapDamper(hold_s=8.0, half_life_s=15.0, max_hold_s=16.0, max_load=1.0)
    flow = snapshot(0, ALPHA, None).flows[0]
    damper.record(flow, BETA, 0.0)
    on_beta = replace(flow, route=BETA, last_switch_s=0.0)
    assert not damper.allows(on_beta, ALPHA, 1.0, 1.0)
    assert damper.allows(on_beta, ALPHA, 1.0, 1.2)


def test_forced_repair_bypasses_damping():
    damper = FlapDamper(hold_s=8.0)
    choose_routes(snapshot(1.0, BETA, None), {"f": 6e5}, damper=damper)
    damper.record(snapshot(1.0, ALPHA, None).flows[0], BETA, 1.0)
    (repair,) = choose_routes(snapshot(1.5, ALPHA, 1.0, alpha_up=False), {"f": 6e5}, damper=damper)
    assert repair.reason == "forced_repair" and repair.link_ids == BETA


def test_zero_hold_disables_and_reset_clears_history():
    off = FlapDamper(hold_s=0.0)
    flow = snapshot(0, ALPHA, None).flows[0]
    off.record(flow, BETA, 0.0)
    assert off.allows(replace(flow, route=BETA, last_switch_s=0.0), ALPHA, 0.1, 0.3)
    on = FlapDamper(hold_s=8.0)
    on.record(flow, BETA, 0.0)
    on.reset()
    assert on.allows(replace(flow, route=BETA, last_switch_s=0.0), ALPHA, 0.1, 0.3)


def test_scorer_split_and_validation():
    rest, damping = split_scorer({"alpha_s": 0.02, "flap_hold_s": 0.0})
    assert rest == {"alpha_s": 0.02} and damping["hold_s"] == 0.0
    assert ReactivePolicy(flap_hold_s=0.0).damper.hold_s == 0.0
    with pytest.raises(PolicyError):
        FlapDamper(hold_s=-1)
