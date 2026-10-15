# Canonical shared specification — version 1.0

This document amends the original guide. Precedence: direct user instructions → this shared spec → session task instructions → original guide. If an existing implementation materially changes feasibility, report the concrete conflict and resolve it within the two existing sessions. Do not silently invent another architecture.

## Scope and ownership

| Session A | Session B |
|---|---|
| Bootstrap; root tooling/locks/CI/README/notices | Forecast features, dataset, models, model cards |
| `src/smartroute/engine/`, `baselines/`, `serialization.py`, `cli.py` | `src/smartroute/intelligence/`, `experiments/`, `dashboard/` |
| `configs/`, `src/smartroute/_vendor/` | `experiment_configs/`, `models/` (small model/metadata only) |
| `tests/engine/`, `tests/contracts/`, starter vendor smoke test | `tests/intelligence/`, `tests/experiments/`, `tests/dashboard/` |
| Root dependency files, `docs/ENGINE.md` | `docs/MODEL_CARD.md`, `docs/RESULTS.md`, `docs/DEMO.md` |
| Final merge and cross-system acceptance | Model training, evaluation and UI integration fixes |

`src/smartroute/contracts.py` is copied from the starter during A0 and then frozen. Neither session may independently revise it. A is the sole editor for a necessary agreed amendment, with a version bump and updated copies in both instruction documents. Generated runtime files go to ignored `artifacts/`. Keep only compact example outputs and final manifests under version control. Neither session overwrites the other's directories to resolve a merge conflict.

Use Python 3.12 for the project, SimPy 4.1.1 for the initially verified extraction, NetworkX, NumPy, pandas, scikit-learn, joblib, Streamlit, Plotly, pytest and a small formatter/linter. Resolve remaining compatible versions and lock them in A0; do not blindly install upstream ns.py or use its pyproject. No environment secrets are required. Optional `SMARTROUTE_ARTIFACT_DIR` defaults to `artifacts/`; paths must resolve inside that project-managed directory for UI writes. UI starts with `python -m streamlit run src/smartroute/dashboard/app.py`; CLI starts with `python -m smartroute.cli` after an editable install.

## The one seam

A exposes `smartroute.engine.sdk.SimulationEngine`, implementing `Engine` below, and `smartroute.baselines.StaticPolicy` / `ReactivePolicy` with no required constructor arguments. B supplies `smartroute.intelligence.policy.PredictivePolicy`, implementing `RoutingPolicy`. The engine imports no B modules. B calls the SDK for training traces, experiments, and dashboard runs. The same RunConfig, Workload, Snapshot, Decision and RunResult are used everywhere; do not introduce a second network or metric implementation in the UI.

The interface includes two methods: `make_workload(config)` returns immutable, pre-generated arrivals; `run(config, workload, policy)` returns a result and calls `reset()` once, then `decide(snapshot)` each interval. The policy sees only Snapshot, not RunConfig traffic segments, scheduled future events, or the future packet trace. This is enforced by the invocation boundary and tests, not just a promise in the report. It is a correctness boundary, not a security sandbox against malicious Python.

Configuration and result persistence are JSON using dataclasses-as-dicts, finite numbers, enum literals as strings, tuples encoded as arrays, sorted keys, UTF-8, and no NaN/Infinity. A provides `save_config(config, path)`, `load_config(path)`, `save_workload(workload, path)`, `load_workload(path)`, `save_result(result, path)`, `load_result(path)` in serialization.py. Paths accept str or pathlib.Path; saves return None and loads return the corresponding dataclass. Loaders reconstruct dataclasses and validate dimensions, IDs, references, types and bounds. Hash canonical compact JSON with sorted keys and separators `(",", ":")`; exclude hash fields themselves. Config hash covers all config fields. Trace hash covers `schema_version`, packet list and the config event list. Save writes atomically. Timing measurements in DecisionRecord are not part of deterministic equality checks. Generated run ID, paths and wall-clock timestamps are metadata outside the core result. Raise typed configuration/policy/engine errors; failed runs do not become zero-valued successful RunResults.

## Immutable contract (copy verbatim)

This exact block appears in both session documents and in `starter/src/smartroute/contracts.py`.

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

## Simulation semantics

- Each LinkSpec is one directed output port plus a wire. A physical bidirectional link is two specs with independent capacities and buffers. No duplicate src/dst pair; isolated nodes are permitted. Use seconds, bits/s, bytes throughout.
- `buffer_bytes` counts **all resident bytes, including the packet in service**. Queue-only bytes are `max(0, byte_size - busy_packet_size)` when using the selected Port. Exact fit accepted; 0 means no packets admitted. No accidental unlimited buffers. Optional observational start/end callbacks may be added around the reused Port service loop to measure exact busy intervals; record modifications and preserve its admission/service/FIFO logic.
- The workload generator is open-loop and policy-independent. Segments do not overlap for one flow, uncovered time means zero load. Constant uses start_bps; linear interpolates start to end; periodic uses `start + (end-start)*(1+sin(2*pi*(t-start)/period))/2`. Nonnegative rates only; period positive. Build arrivals from the rate integral or a documented bounded interval approximation (max 1 ms), with a seeded per-flow initial phase. Do not feed the instantaneous configured rate into the policy; observations count actual source arrivals. Use deterministic digest-derived per-flow seeds, not Python's randomized hash().
- Generate traffic in `[0, warmup+measure)` only. Stable packet IDs are globally unique; trace packet sizes match FlowSpec. Apply source admission even if no path exists, so such packets count as generated and dropped with reason `no_route`. No packet duplication or retransmission.
- Source-route each packet with the flow's route at generation time and a version. Later route changes affect subsequent packets only. Carry hop index and immutable link-ID sequence in adapter-owned packet state. A packet must progress through that sequence; it cannot loop. This avoids forwarding loops from mid-flight routing changes; it does not model distributed convergence.
- Down event: reject new admissions immediately. Previously admitted packets remain resident and use the reused serializer; they finish serialization and are dropped at egress with reason `link_down` if the link is still down. A packet already accepted by Wire completes propagation. If a link recovers before an admitted packet reaches egress, that packet may proceed. This is the explicit simplified failure model.
- Implement failure semantics with admission/egress gates around Port. Queued packets serialize before an egress drop; a link failure does not flush its buffer instantaneously. This deliberate simplification retains the reused service loop. Do not replace it with an undocumented immediate-flush model.
- Capacity changes: positive capacity only; a transmission already started uses the capacity captured by Port for its timeout. Subsequent transmissions use the new rate. A failed link uses an up/down flag, never capacity=0 (Port interprets rate 0 as unlimited).
- At t=0 apply events, take an initial empty-observation snapshot, decide initial routes, then permit arrivals. At later control ticks apply scheduled changes due at that tick before the snapshot, snapshot the preceding interval, decide routes, then admit arrivals timestamped at that tick. Define consistent registration order in SimPy and test exact-boundary cases. Packet completions tied to a tick may fall on the chosen documented side; packet conservation must hold either way. Group scheduled events by timestamp; deterministic tie order is config order. For v1, event timestamps must align to interval_s and lie within the traffic-generation window; reject off-grid events rather than delaying them silently. Source arrivals may occur between ticks.
- After generation stops, run drain_s more seconds; no new packets. Stop control decisions at generation stop. Pending packets remain pending at cutoff. Observation intervals are half-open and consistent. Do not synthesize dropped status for pending packets.
- `busy_s` is the exact intersection of serialization busy intervals with the observation window. It includes partially served packets; `served_bits` counts completed serialization and can exceed capacity*interval in a window containing a boundary completion. UI utilization is `busy_s/interval_s`, not completed-packet bits divided by interval capacity. `attempted_bits` counts all attempts at this link, admitted plus rejected; do not label it source offered demand.
- Each Snapshot contains source `offered_bps` from packet generation counts in the preceding interval, per-link counters for that interval, effective current capacities/up state, resident-byte gauges and the latest flow routes. Snapshots do not reveal future events or traffic. Only past/current snapshots may reach a forecaster.
- Static routing uses fixed baseline propagation + nominal serialization time, updated for availability only; capacity changes do not alter its nominal weights. It repairs a broken route when notified at the same control tick as other policies. Reactive and predictive both use the common candidate scorer below. All policies can choose a longer alternative and handle no-path cases; empty link_ids means no feasible route, since src==dst flows are rejected by validation.

## Controller design

Use NetworkX DiGraph and up to K=4 simple candidate paths per flow, generated by nominal positive delay weights. Include the current path even if outside the first K and still valid. Recompute candidates when availability changes; current capacity affects scoring. K and search overhead are identical for reactive and predictive. Do not enumerate all simple paths. Path ties are broken deterministically by the link-ID sequence.

Demand for reactive = current source offered_bps. Demand for predictive = forecast per-flow average over `[t, t+horizon)`. Build total offered link rates by summing each flow's demand along its current route. Visit flows in a deterministic order rotating by control-tick index. Before scoring a flow, subtract its demand from its current reserved path; add that demand to each candidate to evaluate it. Once the choice is made, reserve it before evaluating the next flow. Demand is an open-loop steady-state projection; explicitly label it estimated, because downstream drops and propagation affect actual link arrivals. This procedure is a small greedy optimizer, not a globally optimal traffic-engineering solution.

For each candidate edge use:

`edge_cost_s = propagation_s + 8*packet_bytes/capacity_bps + 8*resident_bytes/capacity_bps + alpha_s * max(0, projected_ratio - 0.70)^2`

`projected_ratio = projected_offered_bps / effective_capacity_bps` and may exceed 1. Sum edges for path cost. Start alpha_s=0.02, relative improvement threshold=0.10, and cooldown=1 second. Tune these on validation only using a tiny predeclared grid; use the same final values for reactive, persistence, trend and learned predictive controllers. The packet-in-service term double-counts some residual service in this approximation; it is a consistent queue-risk penalty, not an analytical latency prediction.

Normal switch requires `(old_cost-new_cost)/max(old_cost,1e-9) >= threshold` and expired cooldown. Broken/no-path current route bypasses normal cooldown to restore feasibility. Initial route assignment is not counted as a switch. A switch from a valid route to no-route after disconnection is a forced change; reconnect assignment after no-route is also forced except initial setup. Keep forced and ordinary counts explicit. No switch to an empty route just because a valid path has high cost. Log old/new costs, projected peak ratio and the reason; explanation detail can be recomputed from the snapshot and reservation logic for a selected event. The reactive scorer lives in A's baselines/scoring.py; B imports it instead of implementing a second scorer. A exports `choose_routes(snapshot, demand_bps, *, alpha_s=0.02, improvement=0.10, cooldown_s=1.0, k=4)` returning `tuple[RouteChoice,...]`. It is pure for a given snapshot and demand map; tick index is `round(time_s/interval_s)`. Its exact name/signature is part of this seam.

## Forecasting and fair evaluation

Predict a per-flow source rate; output one finite nonnegative rate per flow. Use 10 lag windows (2 seconds) and a 1-second forward-mean label. Historical flow rate, first differences, rolling means/std, and causal trend are allowed. Flow/node/run IDs, scenario labels, future segment parameters, time-to-failure, future queue/load, and trace contents are not model features. Labels are available offline to dataset builders only. Model histories reset each run. The zero-duration t=0 snapshot does not count as a completed window. Fewer than 10 complete windows → explicit persistence warm-up fallback. Invalid/nonfinite outputs or rates outside validation-derived feature support → explicit reactive/persistence fallback. Log status and reason, not a false claim of calibrated confidence.

Models: persistence, clipped causal linear trend, and one small scikit-learn learned model chosen from Ridge or HistGradientBoostingRegressor. A tree regressor may not extrapolate ramps well; measure against trend rather than assuming it wins. Select using train/validation only. Ridge preprocessing fits on train only. No online weight training on test runs. Keep learned-policy result separately even if the validation gate recommends a simpler deployment predictor.

Group split by **workload family ID = topology + scenario parameters + seed**, before constructing windows. All flow rows and all routing-policy variants of the same workload stay in one split. Remove tail windows without a complete future label; no partial labels or crossing run boundaries. Generate training runs under static and reactive policies to expose network-state diversity, but do not leak duplicate source-demand targets across splits. A features/target example does not need queue state because source offered traffic is exogenous in this model. Delayed labels must never be used during online decisions.

Suggested initial split per scenario/topology: train seeds 0–9, validation 100–102, sealed test 200–204. Small smoke mode uses fewer seeds and is never the headline result. Training uses diamond and small-mesh configurations with parameter ranges distinct from a held-out abrupt-spike amplitude/duty cycle. Treat unseen-topology evaluation as secondary; do not call different seeds an unseen traffic family. Freeze split/config hashes, model hash and scorer parameters before opening test results. Report any later changes as a new experiment version, not the same sealed test.

Required policies: static, reactive, predictive-persistence, predictive-trend, predictive-learned. Persistence and reactive may produce identical outcomes with the same current rates/scorer; that is a useful invariant, not a bug to hide. Include a small no-hysteresis ablation on **validation** runs to show stability effects. Final routing benefits are measured over paired runs, not inferred from MAE.

Seven required families: steady low load, gradual ramp, periodic burst, abrupt spike, capacity reduction/recovery, link down/up, competing flows. Use two configurable topologies and several bottleneck choices; avoid designing every test around one easy diamond. Scenario definitions are fixed before model selection. Training/benchmark cost is bounded by short simulated durations and a few flows; profile before increasing them.

Metrics use packets generated in `[warmup_s, warmup_s+measure_s)`, with their terminal status at final drain cutoff. Generated = delivered + dropped + pending exactly for that cohort and each flow; separately retain all-packet ledger invariants. Latency and P95 refer to delivered cohort packets; no deliveries → null. PDR and drop ratio use cohort generated denominator; no generated → null. Throughput is delivered cohort bits divided by measure_s, **including cohort delivery during drain**, labeled “cohort goodput” in UI/report. It is not receive-window throughput. No unrecorded denominator changes. P95 uses NumPy percentile method=linear (verify installed API). For active cohort flows, Jain fairness uses achieved cohort goodput; all-zero vector → null and zero-delivery active flows remain included. Also report per-flow throughput and offered-normalized delivery because unequal demands complicate raw Jain fairness. Unoffered flows are excluded from fairness.

Report MAE/RMSE by flow/workload as well as overall. Packet outcomes within a run are correlated; uncertainty and resampling operate on paired **seed/run units**, not packets. Use mean/SD and paired seed deltas; optional paired bootstrap CI when enough independent seeds exist. Five test seeds are an initial local-project budget, not a strong statistical-power claim. Decision runtime uses perf_counter wall time, reported with hardware/version context, separately from deterministic network metrics. Failed runs have a failure manifest and nonzero CLI status, never filled-in zero metrics.

## Deliverables and fixed acceptance

- Editable install and all advertised commands work on a clean Python 3.12 environment.
- Vendor boundary tests and engine analytical/accounting tests pass.
- All five policies run with identical packet/event trace hashes per paired workload.
- No train/validation/test family overlap; online input boundary and causal feature tests pass.
- A serialized trained model plus schema, versions, split hashes and validation results reloads and predicts in a fresh process.
- Complete benchmark for seven families × two topologies × five test seeds × five policies, or an explicit failed/incomplete manifest that blocks “final complete” status. One scenario can combine competing flows with others, but retain all seven family labels and test coverage.
- Dashboard supports scenario/seed/policy, offered-load multiplier (0.25–2), failure/capacity-event timing where applicable, run/replay, forecast/link views, explanations, policy comparison and CSV/JSON exports. Changes create a new config/trace; they do not mutate a benchmark in place.
- Report positive, neutral and negative outcomes without a fabricated improvement target. No engineering gate requires beating reactive routing.
- A runs final acceptance in the integrated branch; B fixes owned defects within its existing session. No third session, service integration, or paid API is required.
