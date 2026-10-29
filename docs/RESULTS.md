# Measured results — experiment 1.4

## Extended held-out test — 3,500 runs (headline)

Frozen model and the v1.4 controller (with flap damping) on 50 fresh seeds (300–349) that
never appeared in training, validation or the sealed test: 7 scenarios × 2 topologies × 50 seeds ×
5 policies. Audit passed: 3,500 runs, 700 families, zero failures, identical traces per family,
zero pending packets. Intervals: paired percentile bootstrap over 50 seed blocks, 20,000 draws.

| Policy | Delivery | 95% CI | Mean latency (ms) | P95 (ms) | Changes/run |
|---|---:|---:|---:|---:|---:|
| predictive-trend | 96.95% | 96.40–97.50% | 40.86 | 75.66 | 6.20 |
| predictive-learned | 96.40% | 95.63–97.15% | 41.41 | 77.58 | 6.19 |
| reactive | 96.17% | 95.34–96.99% | 41.92 | 76.70 | 6.14 |
| predictive-persistence | 96.17% | 95.32–96.98% | 41.92 | 76.70 | 6.14 |
| static | 84.36% | 82.21–86.44% | 78.24 | 151.13 | 0.29 |

| Comparison (delivery) | Mean difference (pp) | 95% CI (pp) | Better / equal / worse runs | Verdict |
|---|---:|---:|---:|---|
| reactive − static | +11.80 | +10.46 to +13.10 | 572 / 128 / 0 | higher |
| predictive-trend − static | +12.59 | +10.98 to +14.17 | 568 / 132 / 0 | higher |
| predictive-learned − static | +12.04 | +10.63 to +13.39 | 568 / 132 / 0 | higher |
| predictive-trend − reactive | +0.78 | +0.45 to +1.11 | 135 / 495 / 70 | higher |
| predictive-learned − reactive | +0.24 | +0.08 to +0.40 | 67 / 534 / 99 | higher |
| predictive-learned − predictive-trend | -0.55 | -0.83 to -0.27 | 58 / 491 / 151 | lower |

## Flap damping: v1.3 → v1.4 on the same 3,500 workloads

Paired after-minus-before changes per policy (same traces and seeds). See DECISIONS.md for how the
damping parameters were selected on validation seeds only.

| Policy | Delivery before → after | Δ 95% CI (pp) | Changes/run before → after | P95 before → after (ms) |
|---|---:|---:|---:|---:|
| reactive | 89.99% → 96.17% | +5.37 to +6.97 | 18.53 → 6.14 | 98.8 → 76.7 |
| predictive-trend | 92.48% → 96.95% | +3.70 to +5.24 | 17.90 → 6.20 | 97.6 → 75.7 |
| predictive-learned | 91.00% → 96.40% | +4.61 to +6.17 | 18.36 → 6.19 | 98.5 → 77.6 |
| predictive-persistence | 89.99% → 96.17% | +5.36 to +6.97 | 18.53 → 6.14 | 98.8 → 76.7 |
| static | 84.36% → 84.36% | +0.00 to +0.00 | 0.29 → 0.29 | 151.1 → 151.1 |

Every adaptive and predictive policy delivers more than static, and trend beats reactive. The learned
forecaster beats reactive but trails the simpler trend predictor. Static routing does not use the
controller and is identical in both versions. Evidence: `docs/evidence/extended-test/` and
`docs/evidence/v1.3/extended-test/`. The 350-run sealed test follows.

## Sealed test — 350 runs

The complete sealed matrix passed audit: **350 runs**, 70 workload families, zero failures.
Seven scenario families × two topologies × five seeds × five policies. Every paired workload shares its packet/event trace hash.

## Overall outcomes

These are unweighted means of 70 run-level observations per policy, not a pooled packet delivery ratio.

| Policy | Delivery | Cohort goodput (Mbit/s) | Mean latency (ms) | P95 (ms) | Changes/run | Decision time (ms) |
|---|---:|---:|---:|---:|---:|---:|
| predictive-learned | 96.37% | 0.828 | 40.65 | 74.33 | 6.21 | 0.2081 |
| predictive-persistence | 96.24% | 0.827 | 41.52 | 73.56 | 6.10 | 0.0668 |
| predictive-trend | 96.91% | 0.833 | 40.88 | 75.56 | 6.19 | 0.0910 |
| reactive | 96.24% | 0.827 | 41.52 | 73.56 | 6.10 | 0.0212 |
| static | 84.42% | 0.694 | 79.52 | 151.77 | 0.29 | 0.0027 |

## Scenario-level delivery

Mean ± sample SD across ten topology/seed run units per scenario/policy. There are five seeds per topology.

| Scenario | Static | Reactive / persistence | Trend | Learned |
|---|---:|---:|---:|---:|
| capacity | 85.26% ± 4.40% | 99.95% ± 0.16% | 99.95% ± 0.16% | 99.95% ± 0.16% |
| competing | 81.54% ± 15.14% | 99.16% ± 1.80% | 99.16% ± 1.80% | 99.16% ± 1.80% |
| failure | 97.92% ± 4.11% | 99.88% ± 0.34% | 99.86% ± 0.34% | 99.86% ± 0.34% |
| periodic | 78.55% ± 12.49% | 94.58% ± 5.97% | 96.03% ± 5.24% | 95.78% ± 5.58% |
| ramp | 74.80% ± 12.19% | 95.14% ± 4.91% | 95.22% ± 4.97% | 95.19% ± 5.01% |
| spike | 72.85% ± 10.27% | 84.97% ± 12.79% | 88.15% ± 6.59% | 84.62% ± 12.33% |
| steady | 100.00% ± 0.00% | 100.00% ± 0.00% | 100.00% ± 0.00% | 100.00% ± 0.00% |

## Paired differences from reactive

Delivery deltas below use matching topology/scenario/seed runs. SD is across run units, not packets.

| Policy | Mean delivery delta (percentage points) | SD (points) | Better / equal / worse runs |
|---|---:|---:|---:|
| predictive-learned | +0.126 | 1.939 | 9 / 53 / 8 |
| predictive-persistence | +0.000 | 0.000 | 0 / 70 / 0 |
| predictive-trend | +0.670 | 3.693 | 14 / 48 / 8 |
| reactive | +0.000 | 0.000 | 0 / 70 / 0 |
| static | -11.824 | 10.221 | 0 / 14 / 56 |

Persistence and reactive match by design; their packet outcomes are also checked in tests.
Mean delivery versus reactive: learned +0.13 pp, trend +0.67 pp. A lower forecast error does not establish a better routing controller.
Delivered-only latency can fall when delayed packets drop; read it with delivery, drop and pending rates. All final test runs have zero pending packets.

## Forecast accuracy

Validation uses complete one-second future means, after ten completed history windows. Units are bit/s.

| Validation predictor | MAE | RMSE |
|---|---:|---:|
| persistence | 65337.5 | 141594.0 |
| ridge-0.01 | 60686.7 | 109136.1 |
| ridge-1.0 | 60687.0 | 109136.2 |
| ridge-10.0 | 60689.5 | 109136.5 |
| trend | 86159.4 | 184064.2 |

Test accuracy below includes the online predictor's explicit support fallback. It excludes warm-up/tail windows.

| Online predictor | Mean per-flow/workload MAE (bit/s) | Mean per-flow/workload RMSE (bit/s) |
|---|---:|---:|
| predictive-learned | 71121.8 | 89557.5 |
| predictive-persistence | 74541.6 | 98881.9 |
| predictive-trend | 96991.3 | 124180.3 |

## Stability and unseen-traffic stress

The validation-only ablation has 32 runs: two scenarios × two topologies × one seed × four dynamic policies × two guard settings. The no-hysteresis setting removes cooldown, hysteresis and flap damping; scorer alpha and candidate search remain identical.

| Validation setting | Mean delivery | Mean changes/run |
|---|---:|---:|
| default | 100.00% | 3.75 |
| no-hysteresis | 100.00% | 98.00 |

This small ablation compares guard settings on two scenarios only; it is not proof that the chosen guards dominate.
The separate 20-run stress suite uses an unseen abrupt-spike amplitude and duty cycle. It is excluded from the headline matrix.

| Stress policy | Mean delivery |
|---|---:|
| predictive-learned | 74.90% |
| predictive-persistence | 74.01% |
| predictive-trend | 88.53% |
| reactive | 74.01% |
| static | 71.06% |

## Reproducibility and limits

Benchmark wall time: 29.61 seconds on macOS-26.6.2-arm64-arm-64bit / Python 3.12.14. Timing is observational and hardware-specific.
Model SHA256: `63f1f43ddd8c622059a9d0a9940ffbd1c1eb5cd769e1cabcc7a1bcc883b67dda`.
Full manifest SHA256: `257f7c87af4019503f43ce8b7c2de465ea2ab5fbc1e1d36a3cd618e09cf4f396`.
Model/scorer/splits were frozen before sealed evaluation. Experiment 1.4 adds flap damping to the shared controller after route oscillation was observed in the live studio and in v1.3 route-change counts; its parameters were selected on validation seeds only (see DECISIONS.md). v1.3 evidence is retained in docs/evidence/v1.3/.
Reactive remains the preselected dashboard default. Five seeds are a small local-study budget; these results do not establish generality, causality outside this simulator, or statistical significance.
Per-flow/workload forecast errors, offered-normalized delivery, null-preserving aggregates, seed deltas, fairness, drop/pending counts and timings are in docs/evidence/. Full packet ledgers remain in artifacts/final-benchmark/runs/.
Reproduce with the README commands. Run failures are retained and block a complete audit; no failed run is filled with zero metrics.
