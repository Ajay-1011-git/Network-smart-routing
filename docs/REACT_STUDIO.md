# React network studio

The default app is React 19 + TypeScript + React Flow, built by Vite and served at
http://127.0.0.1:8765. `start-studio.sh` builds the frontend and starts the loopback-only
Python service. It does not start or depend on the Streamlit UI. The old UI remains
available separately for archived fixed-scenario report/replay work.

## Editor

- Drag router, switch, workstation, server and cloud devices from the palette, or click
  a palette item to insert one. Drag placed devices to reposition them.
- Drag between device ports to connect them. Alternatively, press C or select the cable
  tool, then click two devices. V selects the movement tool; Escape cancels cable mode.
- Select a device to rename it or edit its IP annotation. Select a wire to set its
  capacity in Mbps, propagation delay in ms, buffer size in KB, or availability.
- A cable represents two independent directed links with the same configured capacity.
  The UI reports the busier direction's service utilization and highlights active routes.
- Add traffic flows with distinct source and destination devices. Adjust offered traffic
  live with the slider or presets. The API accepts 0–10 Mbps per flow; the quick slider
  covers 0–4 Mbps. The capacity input supports 0.01–1000 Mbps; its quick slider covers
  0.05–10 Mbps. Typed values and imported settings remain visible outside slider ranges.
- Pause/resume or advance one 0.2-second control interval. Reset keeps the editable
  network and releases the session. Topology, latency, buffer and policy edits need a
  reset; traffic, capacity and availability changes preserve the live session.
- Network JSON round-trips device positions, handles, labels, cables, flows and policy.
  Runtime telemetry is excluded. JSON import validates dimensions, types, references,
  endpoint uniqueness and numerical bounds. Browser storage autosaves the draft.

The canvas is intended for desktop use and adapts to narrow windows by moving the
inspector underneath the editor. Device types identify visual roles; this is an
open-loop source-routed packet experiment, not a Cisco IOS or Ethernet protocol emulator.

## Live engine

`smartroute.web.live.LiveSession` orchestrates an incremental SimPy environment using the
existing `LinkAdapter`, supplied Port/Wire, canonical dataclasses, `validate_decision`,
static/reactive/predictive policies and `compute_metrics`. It does not implement a second
serializer, path optimizer or network metric formula in JavaScript.

The browser requests a step; the engine advances simulated time by exactly 0.2 seconds.
The next control snapshot observes preceding source arrivals, queues and service spans.
All pending controls are validated before applying changes at the boundary. New source
packets use the current route/version, while in-flight packets retain their immutable
route. Failure admission/egress and capacity-at-service-start semantics match the batch
adapter. Source generation integrates the requested constant rate and preserves packet
credit across control ticks, including packets due exactly at a boundary.

Each cable becomes `<cable_id>:fwd` and `:rev`. Policy decisions see Snapshot only;
requested future traffic changes are not model inputs. Learned policy needs ten completed
observation windows, then checks the same training feature support and fallback rules.
Dynamic scoring retains the shared reference candidate weights documented in DECISIONS.md.

Live metrics use the growing generation cohort `[0, current_simulated_time)`, with
statuses at the current cutoff and no final drain. Goodput is delivered bits divided by
elapsed simulated time, so it is a cumulative live cohort rate. Pending includes queued,
serializing and propagating packets. Mean latency includes delivered packets only. The
traffic chart labels offered rate separately from cumulative cohort goodput. Batch test
metrics and their measurement/drain semantics remain unchanged.

Animation samples successful **wire-entry** events with actual packet IDs, flow IDs,
link directions and route versions. The browser retains a small sample long enough to
animate it at visible speed. Visual position is illustrative and time-dilated, never a
second data plane. Reduced-motion preferences suppress packet animation. All counters
use the complete server ledger.

The top counters show source traffic, delivered packets with the engine's delivery
ratio (delivered ÷ generated so far, so in-flight packets count as not yet delivered),
dropped packets, reroutes and mean latency. Adaptive and predictive policies use the
shared controller's flap damping: a flow that returns to a path it recently left must
first stay put 8 s (doubling per repeat, up to 16 s) unless its current path is
overloaded. Near a link's capacity this keeps the highlighted route steady instead of
switching every second.

## Local API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Engine readiness and observation interval |
| POST | `/api/sessions` | Validate a network, initialize a fresh session |
| POST | `/api/sessions/<id>/step` | Apply optional rates/capacity/availability, advance one tick |
| GET | `/api/sessions/<id>/export` | Initial network, control edit log, current state and packet ledger |
| DELETE | `/api/sessions/<id>` | Release a session |

Sessions are bounded to 32 devices, 64 duplex cables, eight flows, five simulated minutes,
200,000 packets and eight concurrent local sessions. Idle sessions expire after 15
minutes when new sessions are allocated. Requests have a 512 KB input limit; invalid
controls return visible errors. Failed runs never produce fabricated success metrics.
The service binds only to 127.0.0.1, checks browser write origins and does not list directories.

Exported live data has kind `smartroute-interactive-session`, separate from a fixed-trace
RunResult. It includes the original network, timestamped edits and complete packet outcomes.
The UI imports editable network files; it does not pretend an interactive export is a
sealed benchmark or fixed-trace replay. No model pickle uploads are accepted.

## Design and verification

DESIGN.md informs the near-black flat surface stack, electric-blue primary controls,
violet route highlights, square corners and monospace metadata. An original SVG ASCII
globe uses point density and meridians as a restrained geographic texture in the header.
React Flow supplies canvas manipulation; Lucide supplies device/control icons.

Verification includes frontend network round-trips, dangling-reference/invalid-capacity
rejection, deletion cleanup and route labels; live SDK tests cover traffic-triggered
rerouting, forced failover, capacity changes, immutable old packet versions, exact-boundary
source generation, atomic validation, real event identities and ledger conservation.
Real HTTP tests cover creation/step/export/delete, errors, origin checks and static serving.
Browser inspection verified a real low-to-high-demand reroute, live capacity edit, forced
link repair, exported ledger conservation, library insertion and a newly wired two-device
network delivering traffic. The screenshot and acceptance record are in docs/evidence/.
