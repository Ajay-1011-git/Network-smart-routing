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

Experiment **1.3** adds the user-requested React editor and persistent live sessions.
The original immutable contract and batch SDK remain unchanged. The model source hash
now includes the new live/API modules, so training and every benchmark suite were
regenerated with the original data assignments, model grid and scorer settings. The
new interactive sessions have explicitly labeled growing-cohort metrics; they are not
added to the sealed 350-run matrix. The user's React request supersedes the original
pack's Streamlit frontend choice.

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

## Experiment 1.4 — route flap damping

**Observation.** In the live studio, a single flow offered 0.8–1.2 Mbps over the demo's
1 Mbps Alpha path switched between Alpha and the 2.5 Mbps Beta path once per second
(30 changes in 30 s, the cooldown limit). Leaving Alpha empties its queue, so Alpha looks
cheaper again and the flow returns and refills it. v1.3 benchmark runs showed the same
pattern: about 18 route changes per adaptive run, 9 even in the steady scenario.

**Change.** `FlapDamper` in `baselines/scoring.py`, owned by the reactive and predictive
policies, adds an exponential hold-down to *reversals* (returning to a path the flow
voluntarily left): hold_s × 2^penalty, capped at max_hold_s; each reversal adds one to
a penalty that halves every half_life_s. A reversal is damped only while the current
path's projected peak load is ≤ max_load, so a flow is never held on a path it is
overloading. Forced repairs bypass and do not update the damper. Static routing is
unaffected. Cost function, alpha_s, hysteresis, cooldown and candidate search are unchanged.

**Selection (validation seeds 100–102 only, 42 families).** Rule fixed before the sweep:
choose the setting with the fewest mean route changes among those whose mean validation
delivery, for every adaptive policy, is no lower than the undamped controller minus 0.1 pp;
if none qualifies, ship no damping. Three designs were tried, in order:

1. Damp every reversal: route changes 18 → 5–9, but delivery fell 1.5–3 pp in every
   setting. Rejected by the rule.
2. Damp only reversals onto a lightly loaded path: one setting passed on validation but
   in the studio it held flows on an overloaded 1 Mbps path at 1.1–1.2 Mbps
   (147 and 481 drops where undamped had none). Rejected on inspection.
3. Damp only while the current path is not overloaded (shipped): all nine settings
   raised validation delivery (reactive 93.65% → 97.8–98.1%, trend 95.80% → 98.2–98.3%).
   By the rule, hold_s=8, half_life_s=15, max_hold_s=16, max_load=1.0 was selected
   (route changes 18.2 → 4.6). The learned policy, checked on validation afterwards,
   moved 95.01% → 98.39% with 17.7 → 4.4 changes. Sweep: `docs/evidence/flap-damping-validation.json`.

Retraining produced byte-identical model weights (features use routing-independent source
rates); only metadata, source hash and scorer parameters changed. The sealed 350-run test
and the 3,500-run held-out test were then rerun once. The flapping was first noticed via
the studio and v1.3 route-change counts, so v1.4 is not a pre-registered confirmatory
study; its parameters, however, never saw test-seed outcomes. v1.3 evidence is kept in
`docs/evidence/v1.3/`. The no-hysteresis ablation variant also disables damping.
