# Model card

Experiment version: 1.4

Model: StandardScaler+Ridge, Ridge alpha=0.01. Artifact size: 1713 bytes.

Training: 25760 rows / 140 workload families. Validation: 7728 rows / 42 families. Test: 70 disjoint families.

Purpose: estimate each flow's mean source offered rate over the next second from ten completed 0.2-second observations. Rates are open-loop and independent of routing.

Features: lag_9, lag_8, lag_7, lag_6, lag_5, lag_4, lag_3, lag_2, lag_1, lag_0, difference_0, difference_1, difference_2, difference_3, difference_4, difference_5, difference_6, difference_7, difference_8, mean, std, slope. Feature values use Mbit/s; final forecasts use bit/s.

StandardScaler fits on train only. Three predeclared Ridge regularization strengths are compared on validation MAE. The smallest MAE chooses the model, without opening sealed test results. Shared route-scorer defaults are not tuned.

The zero-duration initial snapshot is excluded from history. Warm-up uses persistence. Unsupported features and nonfinite/negative/unsupported learned outputs explicitly fall back to current observed demand, with a logged reason. Support bounds use train/validation extrema plus a margin; they are not uncertainty estimates.

Flow/node IDs, scenario names, seeds, traffic segments, future events and future packets never enter the feature vector. Offline labels are complete future-horizon source packet counts and are unavailable before horizon end. All flows/policy traces in a workload family share one split.

Limitations: sudden unannounced spikes cannot be anticipated reliably. Ridge can underfit periodic bursts; a forecast winner can lose in the routing experiment. The small catalog and seed budget limit generalization. See RESULTS.md and DECISIONS.md.

Model SHA256: `63f1f43ddd8c622059a9d0a9940ffbd1c1eb5cd769e1cabcc7a1bcc883b67dda`. Source SHA256: `b304b658391caf8acbed38a301dbfcf5afe8161f95d6eb8624066de51ab324bf`.

Metadata includes schema, ordered feature names/hash, dependency versions, split hashes/manifests, support bounds, validation scores and the exact scorer. A fresh process reloads the verified artifact. Joblib files are executable: only project-generated trusted model/artifact directories are accepted, and the UI never accepts uploaded models.

The model is included at models/selected/model.joblib. Regenerate with `python -m smartroute.intelligence.train --output models/selected`, then rerun all affected suites. See README for the full sequence.
