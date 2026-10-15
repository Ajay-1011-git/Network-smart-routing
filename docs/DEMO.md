# Local demonstration — React studio

Start from the README's locked Python environment and Node.js 24. Launch:

```sh
./start-studio.sh
```

1. Open http://127.0.0.1:8765. Choose Adaptive routing demo and Start simulation.
   At 0.35 Mbps the path runs through Core Alpha's shorter 1 Mbps links.
2. Press Stress test to raise the same flow to 1.8 Mbps. New packets route through
   Core Beta's 2.5 Mbps alternative. The event log preserves the initial and new routes.
3. Select an active cable and edit its maximum traffic. Changes apply at the next
   control tick. Toggle a cable off to trigger a forced repair, bypassing cooldown.
4. Pause or Step to inspect a single interval. Inspect Traffic and Packet ledger tabs.
   Export simulation data to retain the initial network, live edit log and packet outcomes.
5. Reset or choose Empty workspace. Drag devices from the palette, connect device ports
   or use the cable tool, configure wire capacities, and add source/destination traffic.
   Save/import network JSON to preserve the editable topology and device positions.

IP labels annotate the source-routed simulation; device icons do not emulate Cisco IOS.
Packet motion samples real wire-entry events and slows them for visibility. Queues,
in-flight packets and route versions survive live traffic/capacity/availability changes.
Reset before editing topology, buffer/delay or policy. Live metrics use the growing
generation cohort and no final drain; see REACT_STUDIO.md for exact semantics.

The original Streamlit report viewer remains in src/smartroute/dashboard/ for legacy
fixed-scenario replay and comparison. The React studio is the default user interface.
Batch reproducibility commands and all 350 paired test runs remain available in README.
React checks and browser evidence are recorded in docs/evidence/react-acceptance.json.
