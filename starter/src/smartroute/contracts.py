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
