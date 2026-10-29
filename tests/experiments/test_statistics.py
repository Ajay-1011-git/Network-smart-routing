import pandas as pd
import pytest

from smartroute.experiments.statistics import paired_statistics


def frame(offsets):
    rows = []
    for seed in range(4):
        for topology in ("diamond", "small-mesh"):
            for scenario in ("ramp", "spike"):
                base = 0.8 + 0.01 * seed
                for policy, offset in offsets.items():
                    rows.append(
                        {
                            "seed": seed,
                            "topology": topology,
                            "scenario": scenario,
                            "policy": policy,
                            "variant": "default",
                            "delivery_ratio": base + offset(seed, scenario),
                        }
                    )
    return pd.DataFrame(rows)


def test_identical_policies_have_zero_interval():
    result = paired_statistics(frame({"static": lambda *_: 0.0, "reactive": lambda *_: 0.0}))
    (comparison,) = result["comparisons"]
    assert comparison["mean_delta"] == 0 and comparison["ci95"] == [0, 0]
    assert comparison["equal_runs"] == 16 and comparison["conclusion"] == "inconclusive"
    assert result["seed_blocks"] == 4 and result["cells_per_block"] == 4


def test_constant_paired_gain_is_recovered_exactly():
    result = paired_statistics(
        frame({"static": lambda *_: 0.0, "reactive": lambda s, c: 0.05 if c == "ramp" else 0.01})
    )
    (comparison,) = result["comparisons"]
    assert comparison["mean_delta"] == pytest.approx(0.03)
    assert comparison["ci95"] == pytest.approx([0.03, 0.03])
    assert comparison["better_runs"] == 16 and comparison["conclusion"] == "higher"


def test_varying_blocks_give_interval_around_mean():
    result = paired_statistics(
        frame({"static": lambda *_: 0.0, "reactive": lambda s, c: -0.02 + 0.02 * s})
    )
    (comparison,) = result["comparisons"]
    low, high = comparison["ci95"]
    assert comparison["mean_delta"] == pytest.approx(0.01)
    assert low < comparison["mean_delta"] < high
    assert comparison["worse_runs"] == 4 and comparison["equal_runs"] == 4


def test_missing_run_is_rejected():
    data = frame({"static": lambda *_: 0.0, "reactive": lambda *_: 0.0})
    with pytest.raises(ValueError):
        paired_statistics(data.drop(index=data.index[-1]))
