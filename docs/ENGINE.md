# Engine semantics

`smartroute.engine.sdk.SimulationEngine` is the single simulator used by CLI, datasets,
experiments and dashboard. Every call creates a fresh SimPy environment. Only an immutable
Snapshot enters a policy. Packets follow the source route/version captured at generation;
later decisions affect subsequent packets. No model receives traffic segments or future events.

Each directed link is admission gate → supplied ns.py Port → egress gate → supplied Wire.
Port retains its FIFO/admission/serialization logic. Two optional observation callbacks
record exact service spans and completions. Buffers count all resident bytes, including the
packet in service; exact fit is accepted and zero admits nothing. Opposite directed links
operate independently. Service time is bytes × 8 / capacity; Wire adds propagation.

Traffic generation integrates each configured rate profile on midpoint cells of at most
1 ms, with packet-threshold interpolation inside each cell. A SHA256-derived per-flow
seed controls initial phase. Constant/linear cells integrate exactly, up to packet
quantization; periodic rates use midpoint quadrature. Segment boundaries get separate
cells. No arrivals occur outside the source generation window. A local limit of 250,000
packets bounds accidental oversized runs.

Control ticks use decimal-rounded timestamps (12 places) to avoid 0.6 vs 3×0.2 ordering
drift. At a tick: apply configured events in list order; observe the preceding window;
decide routes; process tied serialization/wire completions; then admit tied source arrivals.
Control events have priority −2, normal SimPy completions priority 1, source arrivals priority 2.
Counters at the control boundary are observed before tied completions. Continuous busy
time uses exact span/window intersections. Events must lie on the control grid.

Down links reject admissions immediately. Already admitted packets serialize, then drop
at egress if still down; recovery before egress permits forwarding. Packets already on a
wire finish propagating. Capacity updates change subsequent transmissions; active service
retains the rate captured when its timeout started. Links never use rate=0 to represent failure.

Control decisions stop at the generation cutoff. The final drain cutoff is exclusive:
events exactly at that time do not execute (SimPy numeric run-until). Unfinished packets
remain pending. No packet is retransmitted, duplicated or silently discarded.

Metrics select packets generated in `[warmup, warmup+measure)` and retain their final
status after drain. Generated = delivered + dropped + pending for each flow and overall.
Cohort goodput includes cohort deliveries in drain and divides by measure duration.
Latency/P95 use delivered packets only; P95 uses NumPy's linear method. Empty denominators
and no deliveries yield null, never NaN. Jain fairness includes all offered flows,
including those delivering zero; an all-zero vector yields null.

The scorer enumerates at most four NetworkX simple candidate paths per flow and retains
the currently valid path. Shared greedy reservations rotate flow order by tick. Static
weights freeze initial capacities; availability repairs can change its route. Dynamic
costs include current serialization, resident bytes and projected offered load; estimates
can exceed capacity. A normal switch needs 10% improvement and a one-second cooldown.
Forced repair/disconnection bypass these guards. `route_changes` is total changes after
initial assignment; `forced_route_changes` is its forced subset. UI reports the difference
as normal changes. See DECISIONS.md for nominal candidate weights on imported topologies.

JSON loaders reconstruct exact dataclasses, reject unknown/missing fields, booleans as
counts, invalid references and nonfinite values, and check ledger-derived metrics.
Canonical hashes normalize typed numeric fields. The trace digest covers schema,
source packet list and scheduled events. Result saves are atomic. Run errors are raised;
the CLI writes a separate failure record and returns nonzero.
