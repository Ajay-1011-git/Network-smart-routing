# Measured results — experiment 1.2

The complete sealed matrix passed audit: **350 runs**, 70 workload families, zero failures.
Seven scenario families × two topologies × five seeds × five policies. Every paired workload shares its packet/event trace hash.

## Overall outcomes

These are unweighted means of 70 run-level observations per policy, not a pooled packet delivery ratio.

| Policy | Delivery | Cohort goodput (Mbit/s) | Mean latency (ms) | P95 (ms) | Changes/run | Decision time (ms) |
|---|---:|---:|---:|---:|---:|---:|
| predictive-learned | 91.38% | 0.766 | 58.14 | 94.98 | 17.73 | 0.1895 |
| predictive-persistence | 90.14% | 0.753 | 61.79 | 99.48 | 18.10 | 0.0598 |
| predictive-trend | 92.43% | 0.773 | 58.34 | 97.07 | 17.59 | 0.0822 |
| reactive | 90.14% | 0.753 | 61.79 | 99.48 | 18.10 | 0.0185 |
| static | 84.42% | 0.694 | 79.52 | 151.77 | 0.29 | 0.0025 |

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

Benchmark wall time: 27.43 seconds on macOS-26.6.2-arm64-arm-64bit / Python 3.12.14. Timing is observational and hardware-specific.
Model SHA256: `63f1f43ddd8c622059a9d0a9940ffbd1c1eb5cd769e1cabcc7a1bcc883b67dda`.
Full manifest SHA256: `4a763f8add5e4a41df200c9302e7867364b87a5b5792056d8b2a65e7e371c9db`.
Model/scorer/splits were frozen before sealed evaluation. Experiment 1.1 regenerates every affected artifact after the documented decimal-boundary correction; no hyperparameters changed after test inspection.
Reactive remains the preselected dashboard default. Five seeds are a small local-study budget; these results do not establish generality, causality outside this simulator, or statistical significance.
Per-flow/workload forecast errors, offered-normalized delivery, null-preserving aggregates, seed deltas, fairness, drop/pending counts and timings are in docs/evidence/. Full packet ledgers remain in artifacts/final-benchmark/runs/.
Reproduce with the README commands. Run failures are retained and block a complete audit; no failed run is filled with zero metrics.
