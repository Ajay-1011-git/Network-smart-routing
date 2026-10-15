# Session B — forecasting, predictive routing, evaluation and dashboard

> Purpose: build the actual intelligence layer and a complete local presentation of measured results. Keep all results tied to Session A's packet engine and metrics.
>
> Alignment: user instructions and `02_SHARED_SPEC.md` override this document; they explicitly amend the supplied guide. Partner Session A owns engine, workload generation, baselines, scorer, SDK, JSON persistence and final merge. You can implement/test your logic with contract fixtures before the engine-ready commit; real training and final results require that commit.

## A. Operating contract

Implement only your owned paths. Read existing code and applicable AGENTS.md before changing it. The shared spec is the implementation authority; the original guide supplies background. Do not refactor unrelated code, replace the chosen foundation, add RL, or introduce another server. Do not spawn agents: this work has a maximum of two Codex sessions.

Verify an external API against the installed package/docs before writing calls. Never invent command output, model scores, paths, license facts, or repository behavior. Import canonical dataclasses; do not redefine them locally. Validate persisted and UI-supplied data at entry points; keep error reasons visible. If a genuine missing user decision blocks dependent work, ask once and keep working on independent tasks. Routine implementation choices and multi-file changes are already authorized: briefly state your plan and continue without confirmation pauses.

For each task: inspect → state a short plan → implement → run its exact VERIFY commands → record real output and any failures → commit with `A<n>:` or `B<n>:` prefix. Commands below define the project's required CLI to implement; they are not claims that these commands exist today. If a tool is unavailable, install the declared dependency in the project environment or report the blocker; do not mark a task passed based on expected behavior. Do not widen scope to fill idle time.

Definition of done for a task: real checks pass, no ownership violations, contracts unchanged, no silent fallback, and a reproducible handoff. Never call a fixture a trained-model result. API keys are unnecessary for this design; do not ask for one.

## B. Canonical specifications

Read `02_SHARED_SPEC.md` for units, timing, failure/capacity semantics, metric windows, scorer, split rules and acceptance. It is required input along with this document. The contract below is copied **verbatim** from `starter/src/smartroute/contracts.py` and is shared with the partner session. Preserve it unchanged and import its types at runtime.

```python
from dataclasses import dataclass
from typing import Literal, Protocol

SCHEMA_VERSION = "1.0"

@dataclass(frozen=True)
class LinkSpec:
    id: str
    src: str
    dst: str
    capacity_bps: float
    propagation_s: float
    buffer_bytes: int

@dataclass(frozen=True)
class FlowSpec:
    id: str
    src: str
    dst: str
    packet_bytes: int

@dataclass(frozen=True)
class RateSegment:
    flow_id: str
    start_s: float
    end_s: float
    kind: Literal["constant", "linear", "periodic"]
    start_bps: float
    end_bps: float
    period_s: float = 1.0

@dataclass(frozen=True)
class LinkEvent:
    time_s: float
    link_id: str
    kind: Literal["down", "up", "capacity"]
    value_bps: float | None = None

@dataclass(frozen=True)
class RunConfig:
    topology_id: str
    scenario_id: str
    seed: int
    nodes: tuple[str, ...]
    links: tuple[LinkSpec, ...]
    flows: tuple[FlowSpec, ...]
    traffic: tuple[RateSegment, ...]
    events: tuple[LinkEvent, ...]
    warmup_s: float = 5.0
    measure_s: float = 30.0
    drain_s: float = 5.0
    interval_s: float = 0.2
    horizon_s: float = 1.0

@dataclass(frozen=True)
class TracePacket:
    packet_id: int
    flow_id: str
    generated_s: float
    size_bytes: int

@dataclass(frozen=True)
class Workload:
    schema_version: str
    trace_sha256: str
    packets: tuple[TracePacket, ...]

@dataclass(frozen=True)
class LinkObservation:
    id: str
    src: str
    dst: str
    up: bool
    capacity_bps: float
    propagation_s: float
    buffer_bytes: int
    resident_bytes: int
    attempted_bits: int
    admitted_bits: int
    served_bits: int
    dropped_packets: int
    busy_s: float

@dataclass(frozen=True)
class FlowObservation:
    id: str
    src: str
    dst: str
    packet_bytes: int
    offered_bps: float
    route: tuple[str, ...]
    last_switch_s: float | None

@dataclass(frozen=True)
class Snapshot:
    schema_version: str
    time_s: float
    interval_s: float
    horizon_s: float
    links: tuple[LinkObservation, ...]
    flows: tuple[FlowObservation, ...]

@dataclass(frozen=True)
class Forecast:
    flow_id: str
    issued_s: float
    horizon_s: float
    rate_bps: float
    model_id: str
    status: Literal["model", "persistence", "trend", "fallback"]
    reason: str

@dataclass(frozen=True)
class RouteChoice:
    flow_id: str
    link_ids: tuple[str, ...]
    reason: str
    old_cost_s: float | None
    new_cost_s: float | None
    projected_peak_load: float | None

@dataclass(frozen=True)
class Decision:
    routes: tuple[RouteChoice, ...]
    forecasts: tuple[Forecast, ...]

class RoutingPolicy(Protocol):
    name: str
    def reset(self) -> None: ...
    def decide(self, snapshot: Snapshot) -> Decision: ...

@dataclass(frozen=True)
class PacketOutcome:
    packet_id: int
    flow_id: str
    generated_s: float
    size_bytes: int
    status: Literal["delivered", "dropped", "pending"]
    terminal_s: float | None
    drop_reason: str | None
    route_version: int

@dataclass(frozen=True)
class FlowMetric:
    flow_id: str
    generated: int
    delivered: int
    dropped: int
    pending: int
    throughput_bps: float
    mean_latency_s: float | None
    p95_latency_s: float | None

@dataclass(frozen=True)
class Metrics:
    generated: int
    delivered: int
    dropped: int
    pending: int
    delivery_ratio: float | None
    drop_ratio: float | None
    throughput_bps: float
    mean_latency_s: float | None
    p95_latency_s: float | None
    fairness: float | None
    route_changes: int
    forced_route_changes: int

@dataclass(frozen=True)
class DecisionRecord:
    time_s: float
    runtime_ms: float
    decision: Decision

@dataclass(frozen=True)
class RunResult:
    schema_version: str
    config_sha256: str
    trace_sha256: str
    policy_name: str
    config: RunConfig
    metrics: Metrics
    flow_metrics: tuple[FlowMetric, ...]
    snapshots: tuple[Snapshot, ...]
    decisions: tuple[DecisionRecord, ...]
    packets: tuple[PacketOutcome, ...]

class Engine(Protocol):
    def make_workload(self, config: RunConfig) -> Workload: ...
    def run(self, config: RunConfig, workload: Workload,
            policy: RoutingPolicy) -> RunResult: ...
```

Environment: Python 3.12. No required secrets. `SMARTROUTE_ARTIFACT_DIR` optionally chooses the artifact root; default `artifacts/`. Pin the verified SimPy 4.1.1 for the extracted components initially. The remaining exact versions are chosen once in A0 by resolving compatible packages. Both sessions use that lock; dependency changes are requested from A. Use project-relative configs in CLI commands and absolute resolved artifact paths internally.


### Target files

- `src/smartroute/intelligence/{features,dataset,predictors,train,model_io,policy}.py`.
- `src/smartroute/experiments/{run,audit,report}.py`.
- `src/smartroute/dashboard/{app,views,fixtures}.py`.
- `experiment_configs/{smoke,train,validation,test}.json` and split manifests.
- `models/` for one compact selected artifact and metadata; large generated artifacts under ignored artifacts/.
- `tests/intelligence/`, `tests/experiments/`, `tests/dashboard/`.
- `docs/MODEL_CARD.md`, `docs/RESULTS.md`, `docs/DEMO.md`.

Import `smartroute.engine.sdk.SimulationEngine` only in the runner/application boundary when the real engine is available. Pure feature/model/policy tests use fixtures. Do not edit A's scorer, baseline classes, CLI, metrics, root locks or contracts; send concrete changes to A with a failing example. Do not maintain a second project/virtualenv inside dashboard/.

## C. Tasks

### B0 · seam fixtures and implementation boundary · P0 · depends: A0

**PROMPT**

Goal: begin useful work immediately on A's bootstrap commit.

Files you may touch: B-owned package/tests/docs directories, `experiment_configs/smoke.json` and temporary ignored artifacts.

Inspect A's shared base and canonical contract. Verify the installed pandas, scikit-learn, Streamlit, Plotly and joblib APIs before using them; ask A to add a missing declared dependency to its root lock rather than creating another requirements file. Build tiny Snapshot fixtures for no-history, growing demand, two alternative paths, disconnected links, and conflicting competing-flow decisions. Fixture Engine/RunResult objects implement the **same** seam; no duplicate dataclasses or metric computation. Store handwritten metrics only as clearly labeled test inputs, never as benchmark observations. Dashboard fixture mode must be explicit in configuration and visible in the UI; real mode must error if engine import is unavailable, not silently fall back to fake results.

**VERIFY**

`python -m pytest tests/intelligence/test_contract_fixtures.py -q`

Verify fixtures serialize to contract field names and the wrong schema/version is rejected. Paste actual output and the A0 base SHA. B0 must not claim that a real simulation/model exists.

### B1 · causal features and split-first dataset · P0 · depends: B0

**PROMPT**

Goal: create forecasting rows whose inference inputs contain only past information.

Files you may touch: `intelligence/features.py`, `intelligence/dataset.py`, `experiment_configs/{train,validation,test}.json`, `tests/intelligence/test_features.py`, `tests/intelligence/test_splits.py`.

Define one feature schema with ordered feature names and its hash. Use 10 **completed** rate-observation windows, causal first differences, rolling mean/std and trend; do not use the zero-duration t=0 snapshot as a completed interval. Compute the next 1-second mean source demand offline from the trace or subsequent observations, aligned to `[t,t+horizon)` and never passed to decide(). Partial tail labels are removed; no mixing across runs. Training and inference call the same feature function. Features reject invalid intervals/missing flows; warm-up is a deliberate missing-feature status, not rows padded with future values.

Create split assignments by topology/scenario-parameter/seed workload-family ID **before** windowing. Persist train/validation/test IDs and hashes. Routing-policy variants and rows of all flows within a family share a split. If a smoke fixture is reused in unit tests, keep it outside the real split manifest. Fit preprocessing only on train. Exclude IDs, traffic parameters, scenario/time-to-event labels and future snapshots from the feature vector. Current flow rate history is observed, not the generator's configured analytic function.

Provide dataset build CLI `python -m smartroute.intelligence.dataset --config experiment_configs/train.json --output artifacts/datasets/train`. It may initially test with fixtures; real CLI mode requires A5. Store row identifiers, feature/label times and split IDs as audit metadata, not model inputs.

**VERIFY**

`python -m pytest tests/intelligence/test_features.py tests/intelligence/test_splits.py -q`

Tests: mutate future traffic and prove earlier features/predictions unchanged; detect same family appearing through two policy traces; prevent windows crossing run boundaries; demonstrate no label availability before horizon end; compare batch features with online history features byte/numerically; reject partial labels. Paste feature names/hash and disjoint split counts from fixture tests, explicitly labeled as fixture evidence until B3.

### B2 · predictors, model persistence and predictive policy · P0 · depends: B1

**PROMPT**

Goal: supply valid forecasts and a controller that reuses A's scorer.

Files you may touch: `intelligence/{predictors,model_io,policy}.py`, `tests/intelligence/test_predictors.py`, `tests/intelligence/test_policy.py`.

Implement persistence and clipped causal linear trend, then a small learned estimator interface. Use Ridge pipeline or HistGradientBoostingRegressor after verifying their real fit/predict and serialization APIs. All model outputs are nonnegative finite bps, with Forecast status/model_id/reason and horizon. Calibrate feature-support bounds and validation fallback rules on training/validation only; do not market min/max or percentile gates as calibrated uncertainty intervals. Out-of-support/invalid output/fewer-than-10-window history uses current observed rate with a logged fallback. A sudden spike cannot be predicted without a learnable precursor; tests/report must show this limitation.

`PredictivePolicy` resets history per run, receives Snapshot only, makes per-flow forecasts, and calls A's `choose_routes` with demand_bps. Policy variants select persistence/trend/learned predictor; all share exactly the same scorer/safeguards. No predicted actual packet drops or phantom future link status. Missing learned artifact produces a visible error for requested learned mode; ordinary warm-up may fall back with logged status. Never silently replace the entire learned run by reactive and label it ML.

Until A4 lands, import the scorer lazily or inject a contract-matching fixture scorer in tests; do not implement another actual routing optimizer. Once A5 is merged, test the real scorer import. Verify a joblib artifact is loaded only from the app's own generated/model directories, not arbitrary UI-uploaded Python pickles. Store schema/version/feature/model/split/dependency hashes alongside it and check compatibility before inference.

**VERIFY**

`python -m pytest tests/intelligence/test_predictors.py tests/intelligence/test_policy.py -q`

Tests cover constant/trend forecasts, finite clipping, reset leakage, cold start, invalid/out-of-support fallback reason, no future access, and artifact metadata mismatch rejection. With A4 present, prove predictive-persistence equals reactive choices for the same complete observed demand/scorer parameters. A toy learned fit is test evidence only, not the final model.

### B3 · merge engine-ready, generate data and select model · P0 · depends: B2, A5

**PROMPT**

Goal: train a real model and freeze evaluation choices before test inspection.

Files you may touch: B-owned training/config/model/docs paths; do not resolve merge conflicts by editing A-owned implementation.

Merge A's engine-ready SHA into your branch. Run the real SDK smoke, validate trace hashes and cohort accounting, and stop real training if engine behavior fails. Generate datasets from static/reactive runs on the declared training workloads. Write the dataset metadata/hashes and actual sample counts; no synthetic random arrays as final training data. Keep the sealed test config assignments fixed and do not inspect their scores during model/scorer tuning.

Train persistence/trend plus a small declared model grid. Tune model and scorer on validation only; coordinate scorer parameter choices with A's public function, without changing defaults in one policy alone. Suggested small scorer grid: alpha_s in {0.01,0.02,0.05}, cooldown_s in {0.5,1,2}, improvement in {0.05,0.10}; reduce combinations with a documented predefined budget before observing outcomes. Avoid a giant Cartesian search; choose a small fixed list of configurations. Share chosen parameters across all dynamic policy variants.

Choose a learned estimator on validation MAE/RMSE, then measure closed-loop network metrics before recommending it. A validation gate may recommend trend/reactive as the default if ML provides no net benefit, but still retain and report the learned policy's own results. Record criteria and selected model/config before evaluating test workloads. Save model artifact, model card, feature schema, train/validation results and split/config hash manifest. No secret API or external LLM is part of forecasting training.

Implement:

`python -m smartroute.intelligence.train --train-config experiment_configs/train.json --validation-config experiment_configs/validation.json --output models/selected`

This orchestrates real dataset generation when absent and refuses stale/mismatched caches. Log phase timing and configuration, not silent progress placeholders.

**VERIFY**

Run the command above and paste real train/validation sample counts, MAE/RMSE for all predictors, chosen settings and artifact hash. Then load the artifact in a **fresh Python process** and predict from a saved causal observation sequence. Run `python -m pytest tests/intelligence -q`. Demonstrate disjoint family IDs from actual manifests. A learned model need not win for B3 to pass, but the result must be real and explicitly compared.

### B4 · paired benchmark, ablations and honest report · P0 · depends: B3

**PROMPT**

Goal: produce the evidence that makes this a network/ML project.

Files you may touch: `experiments/**`, `experiment_configs/**`, `tests/experiments/**`, `docs/RESULTS.md`, bounded result manifests; large outputs under artifacts/.

Build a runner that expands config suites, generates one Workload per resolved config/seed, and reuses it across static/reactive/persistence/trend/learned policies. Reset engine/policy histories each run. Do not allow a policy to see RunConfig traffic or future trace. Use A's metrics and save/load helpers. Write per-run status/config/model/trace hashes, run durations and failure reasons. An incomplete suite returns nonzero with a partial manifest; audit reports missing/failed pairs. Resuming is permitted only when hashes match. Do not replace missing files with zero rows.

The full suite is seven families × two topologies × five test seeds × five policies = **350 routing runs** plus separate training/validation work. Measure a smoke suite first and keep default traffic sizes manageable. All families/topologies need valid baseline paths or intentionally documented disconnect intervals; a label in a manifest is not proof a scenario exercised its intended event. Add assertions or event summaries for each family. Full unseen-traffic stress result must be separately identified from in-distribution seeds. Full unseen-topology generalization is optional.

Report per scenario/policy: cohort mean and P95 latency, PDR, drop/pending rates, cohort goodput, per-flow outcomes, fairness, normal/forced switches, decision runtime and fallback fraction. Include paired seed deltas and variability with the null rules intact. Report per-flow/workload forecast MAE/RMSE separately. Delivered-only tail latency can improve when bad packets drop; interpret it alongside PDR and pending. Include a validation-only no-hysteresis ablation and prediction-error versus routing-outcome examples. Do not tune after opening sealed test scores; if a bug requires changes, record the new experiment version and rerun all affected paired policies.

CLI required:

- `python -m smartroute.experiments.run --suite smoke --output artifacts/smoke`
- `python -m smartroute.experiments.run --suite full --model models/selected --output artifacts/final-benchmark`
- `python -m smartroute.experiments.audit --manifest artifacts/final-benchmark/manifest.json`

Report generation is automatic from manifests/results and excludes failed runs with explicit counts rather than silently narrowing the headline matrix. Final report has all required cases passing; otherwise mark it incomplete. No “AI wins” badge based on one seed or forecast score.

**VERIFY**

`python -m pytest tests/experiments -q`

Run all three commands above. Tests include mismatched traces/model/schema, missing run file, malformed metric, no-traffic/null values, preserving failed status, resume invalidation and duplicate workload rows. Audit must verify expected run count, pairing hashes, accounting, split separation and source/model versions. Paste actual 350-run completion counts, failures and aggregate outcomes. Do not claim completion from smoke mode alone.

### B5 · usable dashboard and replay · P0 · depends: B2; real-mode verification depends: B4

**PROMPT**

Goal: let a reviewer inspect the prediction → routing → measured-outcome loop.

Files you may touch: `dashboard/**`, `tests/dashboard/**`, `docs/DEMO.md`.

Use Streamlit + Plotly in the existing Python package, not a second React/backend app. Verify the installed Streamlit widget/cache/session-state/download APIs and Plotly graph/chart constructors before implementing. Call the real SDK and B policy factories for scenario runs; load persisted RunResult for replay. Cache by config/model/code hashes, never reuse a result across incompatible settings. Fixture mode is available only via explicit development setting and a permanent banner. An absent real engine/model is a visible error. Do not compute separate network metrics in the UI.

Controls: topology/scenario, seed, policy, offered-load multiplier, failure/capacity event time where applicable, run and reset/replay. Changing control values creates a new resolved config/trace. Provide a comparison button that runs all policies on the same immutable workload. Display progress and bounded input sizes; a full 350-run benchmark belongs in CLI, not behind a surprise UI rerun. Do not rerun simulations on every slider movement; explicit Run triggers computation.

Views: directed topology with stable layout, capacities and service-utilization colors; selectable flow/path; current resident/queue pressure; predicted offered link ratios with values above 1 clearly allowed; source actual-vs-predicted forecast chart aligned to issuance/horizon rather than falsely shifting predictions into the past; metrics and paired comparisons; route-decision explanation showing old/new cost and projected load, fallback/model status, and forced/normal reason; packet outcome counts and pending indicator. Replay scrubber selects stored snapshot/decision time. Plotly link path overlays may be custom traces; don't add a new graph dependency for a dozen nodes.

Export selected run config/result JSON, summary CSV, telemetry/forecast CSV and comparison CSV via download buttons. Name units and cohort/drain semantics. No animation-only fabricated packet positions. A replay represents simulated events and sampled state, not real-time packet capture. Display learned-vs-trend/reactive outcomes honestly, including regression and no-switch cases.

**VERIFY**

`python -m pytest tests/dashboard -q`

`python -m streamlit run src/smartroute/dashboard/app.py --server.headless true`

Run AppTest if the installed Streamlit version supports it; otherwise use a small application smoke plus manual/browser inspection and record the limitation. Test that real mode never silently uses fixtures, config changes invalidate cache, invalid params fail visibly, loaded model schema is checked, exports parse through canonical loaders, and selected replay displays the corresponding route. Inspect at least one real congested run and one failure run, with an actual exported file and visible forecast reason. Start-up-only evidence is not full UI acceptance.

### B6 · handoff and integrated defect support · P1, required · depends: B4, B5

**PROMPT**

Goal: give A a complete branch and remain available to finish integration.

Files you may touch: B-owned files only, plus merge metadata. In sequential-only setup you also execute A7's integration checklist after A's handoff, without adding a session.

Run all B tests and complete model/result/demo docs with actual outcomes, limitations and exact reproduction commands. Keep a small selected model and metadata in the chosen artifact strategy so a clean checkout can run learned inference without training first; if model binaries are excluded, provide a single deterministic train command and an honest cold-start UI. Prefer committing a small trusted local model with source/version hashes after checking repository policy. Exclude large packet ledgers/training caches from git. A should be able to locate the full manifests/results locally or reproduce them; do not report an ignored artifact as shipped unless its location is handed off.

Send final commit, engine-ready parent, setup/check commands, model hash/path, split/freeze manifest and full benchmark manifest hash/path to A. If separate machines are used, package generated artifacts as a bounded archive or provide a documented reproducible regeneration command; do not rely on your private filesystem path. Fix integration issues in this same session. If integration changes model inputs, scorer or simulation outcomes, regenerate affected artifacts rather than leaving stale charts.

**VERIFY**

`python -m pytest tests/intelligence tests/experiments tests/dashboard -q`

`python -m ruff check src/smartroute/intelligence src/smartroute/experiments src/smartroute/dashboard tests/intelligence tests/experiments tests/dashboard`

`python -m smartroute.experiments.audit --manifest artifacts/final-benchmark/manifest.json`

Paste real output plus `git diff --name-only <bootstrap-base>...HEAD` and confirm only owned files changed. Do not end with “frontend pending,” “training to be done,” or a fixture benchmark presented as final. Remain ready for A7 defect requests.

## D. Build order and handoffs

No delivery hours were supplied; the windows below establish dependencies without promising an arbitrary duration.

| Window | Work | Exit |
|---|---|---|
| After A0 | B0–B2 with fixtures | Features, predictors and policy tests ready |
| After A5 | B3 | Real engine data, selected artifact, frozen choices |
| Evaluation | B4; B5 UI can start earlier with fixtures | 350 real test runs audited and UI connected |
| Handoff | B6 | Complete commit and artifacts delivered to A |
| Finish | A7 with fixes here | Integrated build passes without a third session |

## E. Final acceptance

1. Features are causal, split grouping prevents policy/flow duplication leakage. ✅ after B1.
2. Predictors, explicit fallback, history reset and shared scorer work. ✅ after B2.
3. A real model is trained, persisted and reloaded, compared with persistence/trend. ✅ after B3.
4. All 350 required test runs and failure/paired-hash audits pass. ✅ after B4.
5. Real-mode UI runs, replays, explains and exports measured results. ✅ after B5.
6. Model card, negative results, reproduction commands and artifact handoff are complete. ✅ after B6.
7. Defects from integrated acceptance are resolved in these same sessions. ✅ after A7.
