# Session A — simulator, baselines and final integration

> Purpose: build the trustworthy packet engine, fixed/reactive policies, immutable workload generation, metrics and command line. Own final merge and acceptance without opening a third session.
>
> Alignment: user instructions and `02_SHARED_SPEC.md` override this document; that spec explicitly amends the original SmartRoute guide. Partner Session B owns prediction, predictive policy, experiments and UI. You can complete engine work with toy policies and contract fixtures before B exists.

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

- Root: `pyproject.toml`, one dependency lock, `.gitignore`, `README.md`, `AGENTS.md`, `THIRD_PARTY_NOTICES.md`, `.github/workflows/ci.yml` if the repo uses GitHub.
- `src/smartroute/contracts.py`: supplied, freeze after bootstrap.
- `src/smartroute/_vendor/ns_py/`: supplied Packet/Port/Wire, license and provenance.
- `src/smartroute/engine/{sdk,adapter,topology,workload,telemetry,metrics,errors}.py`.
- `src/smartroute/baselines/{__init__,static,reactive,scoring}.py`.
- `src/smartroute/{serialization,cli}.py`.
- `configs/topologies/*.json`, `configs/scenarios/*.json` or one documented catalog combining these into RunConfig JSON.
- `tests/engine/`, `tests/contracts/`, `tests/test_vendor_smoke.py`, `docs/ENGINE.md`.

Do not create B's intelligence, experiments or dashboard code. Add `__init__.py` where packaging needs it; preserve a single package tree across both branches.

## C. Tasks

### A0 · bootstrap and contract freeze · P0 · depends: none

**PROMPT**

Goal: produce a shared base from which both sessions can work independently.

Files you may touch: root tooling/locks/docs noted above, supplied starter paths, `tests/contracts/`, and empty package namespace directories only.

Inspect actual repository state first; do not overwrite user changes or initialize over an existing git repository. Copy the starter if not already present. Check the upstream commit/license/provenance. Read the three modules before wrapping them; preserve their service and admission behavior. The imported source needs SimPy, not the complete ns.py 0.5.0 dependency environment.

Create a Python 3.12 project, editable install, a reproducible dependency lock and development commands. Resolve and lock all requirements needed by **both** sessions: SimPy 4.1.1, NetworkX, NumPy, pandas, scikit-learn, joblib, Streamlit, Plotly, pytest and ruff (or one equivalent lint tool). Verify each chosen package is real, installable and exposes the required APIs; do not assume latest versions support 3.12. Explain the selected versions in the lock/README. Add type-checking only if it improves actual boundary checks, rather than adding a second dependency project.

Implement the canonical dataclasses exactly. A serialization task follows; do not freeze guessed APIs for B. Write AGENTS.md with the ownership table, precedence and no-extra-agent/two-session rule. Record borrowed files/commit/license/modifications in THIRD_PARTY_NOTICES.md. Do not copy upstream AGENTS.md as instructions for this application. Add ignored artifact/model-training output paths while retaining a deliberately small model later. Commit bootstrap and give B its hash immediately.

**VERIFY**

`python -m pip install -e '.[dev]'`

`python -m unittest discover -s tests -p test_vendor_smoke.py -v`

`python -c "from smartroute.contracts import SCHEMA_VERSION; print(SCHEMA_VERSION)"`

Run the project's locked install/check command in addition to editable install, and paste actual selected package versions. A0 passes only when imports and all three starter tests pass. Report bootstrap SHA and contract SHA256.

### A1 · topology, config validation and immutable arrivals · P0 · depends: A0

**PROMPT**

Goal: make all policies receive the identical external workload.

Files you may touch: `engine/topology.py`, `engine/workload.py`, `engine/errors.py`, `serialization.py`, `configs/**`, `tests/contracts/**`, `tests/engine/test_workload.py`, `cli.py` config/catalog/trace subcommands.

Implement strict JSON loading into the shared dataclasses. Validate unique node/link/flow IDs, link references, no self flows/parallel directed pairs, finite positive capacities/packet sizes, nonnegative delays/buffers/rates, segment ordering/nonoverlap, valid event references, timing and horizon alignment to interval_s. Reject malformed values including booleans where integer counts are required. Permit disconnected topologies. Include diamond and small mesh, seven scenario families, and catalog resolution to a fully expanded RunConfig. Keep rates/capacities plausible for quick packet simulation; default 1000-byte packets and a few Mbit/s are starting values, not compulsory fixed sizes.

Build pre-generated TracePacket records from open-loop source profiles with seeded phase, stable ordering and global IDs. Hash arrivals plus events as specified. No random draw after the policy starts affects traffic. A canonical trace is reused across runs, not regenerated under each policy. Preserve exact trace JSON round trips. Verify NetworkX DiGraph and path calls against the installed version before use.

Implement CLI:

- `python -m smartroute.cli catalog`
- `python -m smartroute.cli trace --topology diamond --scenario ramp --seed 0 --output artifacts/trace.json`
- Topology/scenario arguments resolve repository defaults; later run command accepts the same options, `--config` for expanded JSON, `--load-multiplier` (0.25–2) and `--event-time-s` where supported. Explicit config and presets are mutually exclusive. Scaling/retiming creates a new config and hash.

**VERIFY**

`python -m pytest tests/contracts tests/engine/test_workload.py -q`

Run catalog and trace commands above. Tests compare same-seed traces byte-for-byte, require a seed-dependent difference when arrivals have randomized phase, check profile integrals within the documented approximation/packet quantization bound, and reject invalid configs. No “same seed” test is satisfied merely by setting a global seed.

### A2 · data-plane adapter and packet accounting · P0 · depends: A1

**PROMPT**

Goal: run an arbitrary validated topology with real queues and exact packet terminal states.

Files you may touch: `engine/adapter.py`, `engine/sdk.py`, `engine/topology.py`, `engine/errors.py`, `tests/engine/test_data_plane.py`, `tests/engine/test_events.py`; minimal observational-hook changes to `_vendor/ns_py/port.py` and its provenance README if required for exact telemetry.

Wire each directed link as admission gate → reused Port → egress gate → reused Wire → next hop/destination. Keep packet identity, generation timestamp, flow, route version and immutable hop sequence in adapter-owned state; use upstream Packet attributes or payload without replacing its serializer. For exact busy-time telemetry you may add small optional start/end observation callbacks around the existing Port service loop, including capacity-at-start. Preserve its Store, admission test, timeout and FIFO behavior; do not reimplement the serializer. Record those modifications and prove unchanged timing/drop semantics with tests. Track drops by comparing admission/drop counters synchronously or by an explicit wrapper; do not infer packet identities from a final aggregate. Every generated packet has exactly one PacketOutcome status. No double completion when multiple gates observe the same object.

Implement Engine's make_workload and run with fresh per-run environments and state. Enforce workload/config hash compatibility, packet times/flows, finite outputs and route validity. Before invoking a policy validate Snapshot; validate Decision coverage, link sequences, uniqueness and forecast values on return. There must be exactly one RouteChoice per configured flow. Nonempty route must connect source to destination without repeated node/link and with currently up links. An empty route is legal only when no path exists; invalid choices raise PolicyError, not invented success. The engine is not responsible for tuning a poor valid path.

Implement the exact failure and capacity rules in the shared spec with flags and gates, not rate=0. Keep queued and in-service packets during a down event as described; document egress-based dropping. Add a deterministic initial-decision/control ordering test. Freeze old packet routes when a policy changes. Stop new arrivals at generation cutoff and drain with pending classification.

Before writing SimPy calls, check the installed Environment/Store/event scheduling API and how run-until handles a boundary timestamp. Decide and document whether cutoff events exactly at drain end execute; apply it consistently in tests and metrics.

**VERIFY**

`python -m pytest tests/engine/test_data_plane.py tests/engine/test_events.py -q`

Tests cover: one packet latency = sum propagation plus serialization; two simultaneous packets serialize FIFO; separate directed links transmit concurrently; exact buffer fill/overflow/zero capacity; capacity change mid-service; failure with queued/in-service/in-wire packets; unavailable path; reroute while old packets drain; and generated=delivered+dropped+pending. Include a negative test where an invalid policy route is rejected. Use tiny analytic cases, not snapshots of your own output as the expected answer.

### A3 · telemetry, metrics and result round trips · P0 · depends: A2

**PROMPT**

Goal: expose causal observations and defensible metrics.

Files you may touch: `engine/telemetry.py`, `engine/metrics.py`, `engine/sdk.py`, `serialization.py`, `tests/engine/test_telemetry.py`, `tests/engine/test_metrics.py`, `tests/contracts/**`.

Implement Snapshot and DecisionRecord creation with exact counters/units, current routes and effective link state. Track busy interval intersections instead of using completed bits as busy utilization. Source rate counts all source-generated traffic, even packets later dropped. No future rates/events enter Snapshot. Accumulate decision wall-clock runtime outside simulated time. Preserve latency/drop/route-change reasons and pending packets.

Implement measurement-cohort metrics and all-flow metrics exactly per shared spec, including null/no-traffic/no-delivery/all-zero-fairness handling. Distinguish queue pressure, service utilization and projected offered ratio in field names and UI-facing helpers. Snapshot uses resident bytes; compute queue-only as a derived gauge if helpful without changing contract. Add serialization save/load functions and schema-version rejection, stable canonical hashes, atomic writes and finite-value validation. Ensure JSON load is not a loose dict cast.

**VERIFY**

`python -m pytest tests/engine/test_telemetry.py tests/engine/test_metrics.py tests/contracts -q`

Evidence includes a hand-computed two-flow result, active zero-delivery flow in fairness, no-offered-traffic case, pending/drain behavior, partial-service busy-window accounting and config/workload/result round trips. Identical runs have equal deterministic outputs after excluding DecisionRecord.runtime_ms only.

### A4 · conventional policies and shared projection scorer · P0 · depends: A3

**PROMPT**

Goal: provide fair static/reactive baselines and the scorer B imports.

Files you may touch: `baselines/**`, `tests/engine/test_routing.py`, `tests/engine/test_stability.py`, `engine/sdk.py` only for policy validation defects.

Expose no-argument StaticPolicy and ReactivePolicy. Implement pure `choose_routes` exactly as specified in shared spec. It must accept a complete nonnegative demand map and score projected demand on each candidate after removing the current flow's reservation. Reserve selected routes sequentially and rotate deterministic processing order. Shared terms, K, cooldown and relative hysteresis are the same for later predictive variants. Empty routes bypass unnecessary cost arithmetic. Keep initial static nominal weights frozen per run while repairing availability at control ticks.

Use NetworkX for candidate generation; verify the actual installed shortest_simple_paths API and iterator behavior before implementing K limits. Exclude down links by building an up-link view and invalidate candidates on changes. Do not enumerate exponentially many paths to find four. Capture detailed reason codes and distinguish initial assignment, normal switch, forced repair and disconnection. Preserve constant-demand decisions across repeated calls when state is unchanged and cooldown rules apply.

**VERIFY**

`python -m pytest tests/engine/test_routing.py tests/engine/test_stability.py -q`

Tests include analytic shortest path; disconnected graph; low-load route retained; projected candidate becomes overloaded after adding the flow; two competing flows avoid a simultaneous empty-link stampede; cooldown and improvement boundary; failure bypass; and no cycles. A stub policy supplying current observed demands must match ReactivePolicy decisions; B later verifies predictive-persistence equivalence.

### A5 · complete engine CLI and early handoff · P0 · depends: A4

**PROMPT**

Goal: let B generate real datasets without importing your test internals.

Files you may touch: `cli.py`, `engine/sdk.py`, `serialization.py`, `docs/ENGINE.md`, root dependency metadata only if necessary, `tests/engine/test_cli.py`.

Provide `python -m smartroute.cli run --topology diamond --scenario ramp --seed 0 --policy reactive --output artifacts/reactive.json`, plus static policy, `--trace artifacts/trace.json`, `--config`, and overrides already specified. Auto-create workload if not supplied; same resolved config gives the same trace. Return nonzero exit on validation/policy/engine failures, print actionable errors and preserve structured failure metadata outside RunResult. Use a documented factory for policies; adding B's choices must use lazy imports after their code is merged so engine-only install/tests still work. B's CLI entry points live in its modules rather than modifying yours.

Send engine-ready commit immediately when SDK, both baselines, scorer and JSON helpers pass. Include a compact valid result fixture with explicit fixture metadata in its filename/docs, shape and output hash; do not label a hand-built result a benchmark. Demo fixtures live in tests/contracts/fixtures, generated files in artifacts.

**VERIFY**

`python -m pytest tests/engine tests/contracts -q`

`python -m smartroute.cli run --topology diamond --scenario ramp --seed 0 --policy static --output artifacts/static.json`

`python -m smartroute.cli run --topology diamond --scenario ramp --seed 0 --policy reactive --output artifacts/reactive.json`

Load both through load_result and paste trace hashes plus metrics. Require equal workload hashes and packet identity/timestamps; differing delivery outcomes are allowed. Report engine-ready SHA and remaining limitations.

### A6 · reproducibility and delivery hardening · P1, required · depends: A5

**PROMPT**

Goal: make the engine maintainable while B trains and integrates.

Files you may touch: A-owned tests/docs/root tooling/configs; minimal A engine/baseline fixes justified by a failing check.

Run all seven families on both topologies with static/reactive smoke seeds. Profile wall time and packet counts, bound configuration sizes for local UI operation and avoid giant synchronous UI runs. Update README install/CLI commands and ENGINE semantics, notices, clean install instructions and CI. CI should run small meaningful smoke cases, not retrain the full model on every push. Make sure distribution packaging includes the vendored license/provenance and configs can be resolved outside the repository cwd (or explicitly require repository cwd and validate it). Keep binary artifacts bounded. Do not invent performance claims while B's experiments are pending.

**VERIFY**

`python -m pytest tests/engine tests/contracts -q`

`python -m ruff check src/smartroute/engine src/smartroute/baselines src/smartroute/contracts.py src/smartroute/serialization.py src/smartroute/cli.py`

Run a fresh locked install using the documented command and repeat one run. Report 14-case smoke matrix statuses and a measured representative run duration with topology/packet count/hardware. Fix only real failures; avoid cosmetic work that delays integration.

### A7 · merge and final acceptance in this same session · P0 · depends: A6, B6

**PROMPT**

Goal: deliver the complete project on one integrated branch.

Files you may touch: A-owned code/docs/root files and merge metadata. B-owned defect fixes stay with B; request them in the existing B conversation. Sequential-only setup transfers this task to Session B after A hands over.

Before merge confirm clean worktrees and agreed base. Merge B's final commit with history preserved; resolve root dependency files as sole owner, keeping pinned compatibility. Do not replace B's files with A's versions or delete failures. Run full suite and smoke end-to-end after merge. B's full benchmark artifacts may be reused when config/model/source hashes remain valid and only unrelated docs changed; rerun affected experiments if integrated code changes behavior. Check model card, split manifest, test freeze, benchmark completeness and report-to-artifact consistency.

Launch the real Streamlit UI and inspect its controls/views with a browser when available; otherwise perform headless startup and record the missing visual inspection explicitly. Run a real scenario, replay its topology, inspect a reroute reason and download an export. No test fixture may masquerade as the real engine. Keep UI fixture mode visibly labeled.

**VERIFY**

`python -m pytest -q`

`python -m ruff check src tests`

`python -m smartroute.experiments.run --suite smoke --output artifacts/final-smoke`

`python -m smartroute.experiments.audit --manifest artifacts/final-benchmark/manifest.json`

`python -m streamlit run src/smartroute/dashboard/app.py --server.headless true`

Paste real command output, integrated commit, actual dashboard URL, model/manifest paths and remaining failures. “Complete” requires successful real-mode UI plus audited full benchmark; if a gate fails, keep both existing sessions working until resolved, or state a concrete external blocker rather than invent a pass. No guaranteed ML gain is required.

## D. Build order and handoffs

No calendar deadline was supplied; these are order windows, not fabricated hour estimates.

| Window | Work | Exit |
|---|---|---|
| Bootstrap | A0 | B can branch on immutable shared base |
| Parallel core | A1–A4 while B0–B2 use fixtures | Engine/scorer are validated |
| Engine-ready handoff | A5 | B merges engine-ready; real data can start |
| Parallel finishing | A6 while B3–B6 train/build UI | Both module checklists pass |
| Integration | A7 with B fixes in same sessions | One working repository and report |

## E. Final acceptance

1. Bootstrap lock and immutable contract available to B. ✅ only after A0 evidence.
2. Packet service, finite buffers, failure and cohort accounting have analytic tests. ✅ after A2–A3.
3. Static/reactive and scorer follow shared semantics and causal snapshots. ✅ after A4.
4. SDK/CLI/results work independently of B and paired hashes agree. ✅ after A5.
5. Clean install, notices, 14-case smoke and CI pass. ✅ after A6.
6. B's model, five-policy evaluation and dashboard work on the integrated commit. ✅ after A7.
7. No unresolved required gate, hidden fixture, omitted failed run or fabricated improvement. ✅ after final audit.
