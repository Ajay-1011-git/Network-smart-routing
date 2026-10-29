# Measured results

## Extended held-out test — 3,500 runs (headline)

Same frozen model, scorer and engine as experiment 1.3, on 50 fresh seeds (300–349) that never
appeared in training, validation or the original test: 7 scenarios × 2 topologies × 50 seeds ×
5 policies. Audit passed: 3,500 runs, 700 families, zero failures, identical traces per family,
zero pending packets. Intervals: paired percentile bootstrap over 50 seed blocks, 20,000 draws.

| Policy | Delivery | 95% CI | Mean latency (ms) | P95 (ms) | Changes/run |
|---|---:|---:|---:|---:|---:|
| predictive-trend | 92.48% | 91.19–93.77% | 57.33 | 97.63 | 17.90 |
| predictive-learned | 91.00% | 89.55–92.48% | 59.43 | 98.46 | 18.36 |
| reactive | 89.99% | 88.38–91.60% | 61.74 | 98.79 | 18.53 |
| predictive-persistence | 89.99% | 88.38–91.56% | 61.74 | 98.79 | 18.53 |
| static | 84.36% | 82.21–86.44% | 78.24 | 151.13 | 0.29 |

| Comparison (delivery) | Mean difference (pp) | 95% CI (pp) | Better / equal / worse runs | Verdict |
|---|---:|---:|---:|---|
| reactive − static | +5.62 | +5.08 to +6.17 | 504 / 196 / 0 | higher |
| predictive-trend − static | +8.12 | +7.15 to +9.08 | 508 / 192 / 0 | higher |
| predictive-learned − static | +6.63 | +5.93 to +7.34 | 508 / 192 / 0 | higher |
| predictive-trend − reactive | +2.49 | +2.00 to +2.98 | 156 / 540 / 4 | higher |
| predictive-learned − reactive | +1.01 | +0.78 to +1.25 | 71 / 615 / 14 | higher |
| predictive-learned − predictive-trend | -1.48 | -1.90 to -1.08 | 37 / 542 / 121 | lower |

Every adaptive and predictive policy delivers more than static, and trend beats reactive.
The learned forecaster beats reactive but delivers less than the simpler trend predictor, as in
the original test. Evidence: `docs/evidence/extended-test/`. The original 350-run sealed test follows.

## Original sealed test — experiment 1.3

The complete sealed matrix passed audit: **350 runs**, 70 workload families, zero failures.
Seven scenario families × two topologies × five seeds × five policies. Every paired workload shares its packet/event trace hash.

## Overall outcomes

These are unweighted means of 70 run-level observations per policy, not a pooled packet delivery ratio.

| Policy | Delivery | Cohort goodput (Mbit/s) | Mean latency (ms) | P95 (ms) | Changes/run | Decision time (ms) |
|---|---:|---:|---:|---:|---:|---:|
| predictive-learned | 91.38% | 0.766 | 58.14 | 94.98 | 17.73 | 0.2048 |
| predictive-persistence | 90.14% | 0.753 | 61.79 | 99.48 | 18.10 | 0.0640 |
| predictive-trend | 92.43% | 0.773 | 58.34 | 97.07 | 17.59 | 0.0883 |
| reactive | 90.14% | 0.753 | 61.79 | 99.48 | 18.10 | 0.0195 |
| static | 84.42% | 0.694 | 79.52 | 151.77 | 0.29 | 0.0027 |

## Scenario-level delivery

Mean ± sample SD across ten topology/seed run units per scenario/policy. There are five seeds per topology.

| Scenario | Static | Reactive / persistence | Trend | Learned |
|---|---:|---:|---:|---:|
| capacity | 85.26% ± 4.40% | 99.03% ± 1.27% | 99.03% ± 1.27% | 99.03% ± 1.27% |
| competing | 81.54% ± 15.14% | 87.49% ± 12.71% | 87.49% ± 12.71% | 87.49% ± 12.71% |
| failure | 97.92% ± 4.11% | 99.61% ± 0.59% | 99.61% ± 0.59% | 99.61% ± 0.59% |
| periodic | 78.55% ± 12.49% | 87.00% ± 10.55% | 94.06% ± 5.70% | 94.81% ± 6.00% |
| ramp | 74.80% ± 12.19% | 79.95% ± 11.88% | 79.95% ± 11.88% | 79.95% ± 11.88% |
| spike | 72.85% ± 10.27% | 77.89% ± 10.23% | 86.84% ± 5.62% | 78.76% ± 9.43% |
| steady | 100.00% ± 0.00% | 100.00% ± 0.00% | 100.00% ± 0.00% | 100.00% ± 0.00% |

## Paired differences from reactive

Delivery deltas below use matching topology/scenario/seed runs. SD is across run units, not packets.

| Policy | Mean delivery delta (percentage points) | SD (points) | Better / equal / worse runs |
|---|---:|---:|---:|
| predictive-learned | +1.241 | 4.097 | 9 / 61 / 0 |
| predictive-persistence | +0.000 | 0.000 | 0 / 70 / 0 |
| predictive-trend | +2.287 | 5.427 | 16 / 54 / 0 |
| reactive | +0.000 | 0.000 | 0 / 70 / 0 |
| static | -5.722 | 5.869 | 0 / 20 / 50 |

Persistence and reactive match by design; their packet outcomes are also checked in tests.
The learned predictor improves aggregate delivery over reactive here, while trend performs better overall. A lower forecast error does not establish a better routing controller.
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

The validation-only ablation has 32 runs: two scenarios × two topologies × one seed × four dynamic policies × two guard settings. Scorer alpha and candidate search remain identical.

| Validation setting | Mean delivery | Mean changes/run |
|---|---:|---:|
| default | 97.71% | 20.00 |
| no-hysteresis | 100.00% | 98.00 |

Removing cooldown/hysteresis trades extra switching for delivery in these cases; this is a stability tradeoff, not proof the chosen guards dominate.
The separate 20-run stress suite uses an unseen abrupt-spike amplitude and duty cycle. It is excluded from the headline matrix.

| Stress policy | Mean delivery |
|---|---:|
| predictive-learned | 74.90% |
| predictive-persistence | 74.01% |
| predictive-trend | 88.53% |
| reactive | 74.01% |
| static | 71.06% |

## Reproducibility and limits

Benchmark wall time: 28.94 seconds on macOS-26.6.2-arm64-arm-64bit / Python 3.12.14. Timing is observational and hardware-specific.
Model SHA256: `63f1f43ddd8c622059a9d0a9940ffbd1c1eb5cd769e1cabcc7a1bcc883b67dda`.
Full manifest SHA256: `b7614e1296b918007b7ac773b9a5dfcd429eaf84f44701aba136dcd19b9a3fba`.
Model/scorer/splits were frozen before sealed evaluation. Experiment 1.3 regenerates the source-verified matrix for the React/live API addition. Earlier boundary corrections are documented in DECISIONS.md; no hyperparameters changed after test inspection.
Reactive remains the preselected dashboard default. Five seeds are a small local-study budget; these results do not establish generality, causality outside this simulator, or statistical significance.
Per-flow/workload forecast errors, offered-normalized delivery, null-preserving aggregates, seed deltas, fairness, drop/pending counts and timings are in docs/evidence/. Full packet ledgers remain in artifacts/final-benchmark/runs/.
Reproduce with the README commands. Run failures are retained and block a complete audit; no failed run is filled with zero metrics.
