# Implementation decisions and limits

The supplied pack starts from vendor components only. This repository implements its A
and B modules sequentially in one chat, retaining the canonical contract unchanged. No
additional agents, services, paid APIs or separate frontend were introduced.

For a bounded local study, catalog runs use 2 seconds warm-up, 10 seconds measurement,
2 seconds drain, 0.2-second observations and a 1-second forecast horizon. The dataclass
defaults remain untouched. Nominal links are 1 Mbit/s, buffers 16 KB, packets 1000 bytes.
Train/validation/test share a predeclared load range and periodic-period range; the stress
suite changes abrupt-spike amplitude/duty cycle outside those settings. Seed variation
changes source phase and bottleneck choice. Small mesh adds alternate hops/cross links;
it is not a claim of unseen-topology generalization.

The public pure `choose_routes(snapshot, demand_map)` seam does not carry original
capacities. Candidate enumeration therefore uses a fixed nominal 1 Mbit/s reference,
which exactly matches both supplied topologies and stays unchanged during capacity events.
Actual scoring always uses observed effective capacity. For imported configurations with
heterogeneous nominal capacities, enumeration uses this documented reference rather than
unavailable original capacities. Static routing freezes the actual initial observed
capacities. This is a limitation for arbitrary imported topologies; it does not affect
the catalog's nominal weights. Candidate enumeration caches are keyed by the full
available-edge description, endpoints, packet size and K.

Experiment 1.0 was an implementation check. An extra exact-boundary test identified
decimal tick drift (3×0.2 versus 0.6). Experiment **1.1** rounds control timestamps to
12 decimal places. The model, validation data and all paired test/stress/ablation runs
were regenerated. No hyperparameters were changed after test inspection.

Experiment **1.2** adds stricter replay validation (packet/event digest, complete control
timeline, telemetry bounds and stored route decisions) and checks the learned model's
trained observation interval/horizon before inference. Training and every experiment
suite were regenerated again with the same frozen configurations and hyperparameters.

The learned estimator is StandardScaler + Ridge over ten source-rate lags, nine causal
differences, mean, population std and slope. Rates are expressed in Mbit/s for features.
Preprocessing fits on train only. Alpha ∈ {0.01, 1, 10} is selected on validation MAE.
Scorer defaults are fixed without a search. Feature support is an extrema check over
train/validation with a 5% margin, not calibrated uncertainty. Negative/nonfinite or
unsupported predictions fall back explicitly. There is no online weight fitting.

The model's future-mean label is available offline only after the horizon ends. Family
IDs hash the expanded configuration including seed, before windows are built. All flows
and static/reactive source traces from a family stay together. Tail windows without a
complete label are removed. Training rows duplicate source targets across policy
variants within their assigned split, never across splits.

Results describe open-loop packet traffic and a small greedy controller. They do not
model TCP feedback, distributed convergence or real internet deployment. Five test seeds
per topology/family are a local project budget. Delivered-only latency must be read
alongside delivery/drop/pending ratios. No publication novelty or universal ML advantage
is claimed. Local joblib artifacts are trusted executable files, checked against metadata;
hash checks detect stale/corrupted artifacts and do not authenticate an untrusted publisher.
