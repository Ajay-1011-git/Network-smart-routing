# Project review and reuse decision

Review date: 15 October 2026. Input: `SmartRoute_AI_Project_and_Repository_Guide.md`. Repository facts below were checked through current GitHub files; source inspection and the narrow smoke test are distinguished from a complete application audit.

## What the project is

A reproducible packet-network experiment: generate traffic → queue/transmit packets → observe demand → forecast demand → select routes → compare measured outcomes against conventional controllers. The credible contribution is an evaluated prediction-assisted controller with stability safeguards. A network animation or an “AI beats Dijkstra” screenshot alone is insufficient evidence. This is not a deployment of a real internet routing protocol, TCP implementation, or an SDN controller.

The original guide already makes good choices: conventional baselines, real queues and drops, held-out runs, route stability, and negative-result reporting. Its main gaps are the foundation, forecast target, effect of intervention, exact event semantics, and the division into two buildable modules.

## Decisions that improve the guide

| Original gap | Decision in this pack | Why it helps |
|---|---|---|
| Recommended foundation uses real-time threads and sleeps | Use SimPy with selected ns.py Packet/Port/Wire components | Reuse queue/service code while making simulated time deterministic |
| Future link utilization is the first target | Forecast **source offered rate per flow**, then map it to candidate routes | Busy fraction saturates at 1; source demand retains overload information and is less directly altered by rerouting |
| An unloaded alternative can appear artificially free | Evaluate projected link load after adding/removing the flow; update reservations between flow decisions | Avoid rerouting all flows onto the same apparently empty link |
| Forecast quality and routing benefit can be conflated | Compare persistence, trend, learned prediction and reactive control with the same path scorer | Isolate whether ML adds value |
| Feature windows and labels are loose | 0.2-second observations, 1-second forward-average target, grouped run splits | Makes training and inference agree and blocks overlapping-run leakage |
| Failure and in-flight semantics are unspecified | Freeze routes per packet; define drop/no-route/in-flight handling | Prevent loops, disappearing packets and ambiguous metrics |
| One seed may still generate policy-dependent traffic | Pre-generate immutable packet/event traces and hash them | Same packet IDs, sizes and arrival times for every policy |
| UI/API add many moving parts | Streamlit + Plotly calls the same SDK as CLI | Complete local demonstration within two coding sessions |
| “Done” could depend on AI winning | Engineering acceptance is fixed; scientific results may be positive, neutral, or negative | Avoid pressure to manipulate benchmarks |

Per-flow demand forecasting is an intentional amendment, not something already implemented in the uploaded guide. Predicted **link offered-load ratios** remain visible in the UI and are the controller input after aggregation. Source demand is still a limited abstraction: this project uses open-loop application traffic, so it does not claim to model TCP congestion feedback.

## Repositories to reuse

### 1. TL-System/ns.py — selected source reuse, recommended

URL: https://github.com/TL-System/ns.py

Audited revision: `7218b680a72a59b30bc3271d8ca0965d8556cee9`.

Read: root listing, LICENSE, pyproject.toml, `ns/packet/packet.py`, `ns/port/port.py`, `ns/port/wire.py`. Root license is Apache-2.0. Port performs size-bytes × 8 / bit-rate serialization and finite admission; Wire adds propagation delay. These fit the required data plane better than the original recommended foundation.

**Reuse shipped in starter:** those three files, relocated under `smartroute/_vendor/ns_py/`, full upstream LICENSE, provenance, and only package-local import changes. Build your adapter, routing, telemetry, and experiments around them. Avoid copying the full repository. Preserve relevant notices and record additional modifications.

**Compatibility finding:** the fetched 0.5.0 pyproject requires Python >=3.14 excluding 3.14.1 and specifies a broader dependency stack. The README's Python 3.13 setup text does not match that declaration. Blindly installing the latest whole package on Python 3.12 is therefore a poor plan. The three selected modules use a smaller dependency surface; their smoke tests passed on Python 3.12.14 with SimPy 4.1.1. This is evidence for the extraction only.

### 2. ComputerNetworksVIT/Network-Routing-Simulator — reference; optional topology reuse

URL: https://github.com/ComputerNetworksVIT/Network-Routing-Simulator

Confirmed MIT root license, copyright Yashwanth K, 2025. `link.py` creates unbounded queues and starts a thread for each send, sleeps for latency, then enqueues the packet. It does not implement the finite-capacity serializer required here. Rebuilding that data plane and replacing Tkinter would erase much of the apparent head start.

Do not fork this as the application foundation. Its JSON topology ideas or selected topology data can be reused with the MIT notice if useful; NetworkX already supplies shortest-path logic, so copying its router classes is unnecessary. None of this repository's files are included in the starter.

### 3. NetworkX — dependency reuse

Use its graph representation, Dijkstra/shortest-path functions, and the first K loop-free candidates from `shortest_simple_paths`. Use a DiGraph, not a MultiDiGraph: the inspected API does not support Multi[Di]Graph inputs. Represent opposite directions as separate links. Do not write your own Dijkstra or Yen implementation. Verify API behavior against the pinned version during bootstrap.

### 4. SimPy, scikit-learn, Streamlit, Plotly — dependencies

Reuse event scheduling, regression implementations, model evaluation utilities, UI widgets, and chart rendering. Your code should be domain glue and experiment logic. Verify real APIs before calling them and lock versions that actually install together. No specific Streamlit/Plotly release was runtime-validated in this review.

## Existing guide's other repositories

| Repository | Decision for this build | Evidence status |
|---|---|---|
| rayyan-merchant/DRL-Adaptive-Routing | Architectural reading only; do not import DQN/ns-3 stack | Current root listing inspected; no root LICENSE present. Guide's deeper metric findings were not rerun here |
| kishorekrrish3/NetRouteAI | UI inspiration only; code not needed | Current search excerpt lists README/app/requirements; guide reports license unresolved |
| knowledgedefinednetworking/DRL-GNN | Research extension after completion | Guide reports BSD-3-Clause; not independently re-audited here |
| BNN-UPC/RouteNet-Fermi | Research extension after completion | Guide reports Apache-2.0 and older ML dependencies; not re-audited here |
| knowledgedefinednetworking/a-deep-rl-approach-for-sdn-routing-optimization | Research reading | Guide reports MIT and OMNeT++; not a drop-in packet engine |
| pavni006/Congestion-Aware-Network-Traffic-Simulator | Requirements reference | Guide reports unresolved source license; no copying authorized by this pack |
| Sencer49/link-state-simulator | Architecture reference | Guide reports unresolved source license; no copying authorized by this pack |
| rapariciopardo/PRISMA, tkn-tub/ns3-gym, milanalay/DRL_SDN | Exclude from required build | Guide reports GPL licenses and a heavier/different problem stack; no need for these dependencies |

Public visibility is not a license grant. This is a practical reuse inventory, not a full legal audit. A source with unresolved licensing is not needed to finish this design.

## What was actually tested

On Python 3.12.14 and SimPy 4.1.1, the selected components accepted two of three simultaneous 10-byte packets with a two-packet resident limit, dropped one, and delivered at 1.01 and 2.01 seconds for an 80-bit/s port plus 0.01-second propagation. A zero-capacity port dropped all three. Repeating the run reproduced arrivals and drop counts. The relocated starter's three unittest checks were also run before delivery.

This does not validate failure wrappers, live capacity changes, packet accounting, forecasters, benchmarks, or UI; the build tasks explicitly test those next. No claim is made that SmartRoute is already built or that ML has improved routing.

## Novelty and scope

Prediction-assisted routing is an established idea. Do not describe this as the first AI routing system. A defensible project contribution is the combination of intervention-aware demand projection, controlled stability/fallback behavior, and reproducible paired experiments with ablations. Any novelty claim requires a separate literature comparison; this pack does not establish publication novelty.

Keep seven scenario families, two small topologies, one learned model selected against simple predictors, and a usable local dashboard. Cut RL, GNNs, LSTMs, real packet capture, authentication, cloud deployment, databases, and a separate React server from required scope.

## Primary references

- Audited source: https://github.com/TL-System/ns.py/tree/7218b680a72a59b30bc3271d8ca0965d8556cee9
- Upstream license: https://github.com/TL-System/ns.py/blob/7218b680a72a59b30bc3271d8ca0965d8556cee9/LICENSE
- Original candidate link: https://github.com/ComputerNetworksVIT/Network-Routing-Simulator/blob/main/link.py
- Original candidate license: https://github.com/ComputerNetworksVIT/Network-Routing-Simulator/blob/main/LICENSE
- SimPy scheduling: https://simpy.readthedocs.io/en/latest/topical_guides/time_and_scheduling.html
- NetworkX candidates: https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.simple_paths.shortest_simple_paths.html
- Grouped and time-aware evaluation: https://scikit-learn.org/stable/modules/cross_validation.html
