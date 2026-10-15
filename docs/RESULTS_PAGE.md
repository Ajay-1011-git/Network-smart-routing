# Results page and launcher

Open `http://127.0.0.1:8765/#results`, or use Results in the studio navigation.
The page retains the DESIGN.md palette, globe, restrained mono labels, and flat panels.

## Measurement sources

The benchmark graphs and tables come from `docs/evidence/report.json` and the
350 rows in `docs/evidence/summary.csv` (experiment 1.3). The generator checks
completion, pairing, disjoint splits, source identity, row counts, and aggregate
delivery, latency, and goodput against the underlying records before publishing.
The fifth benchmark policy is predictive-persistence, equivalent to reactive;
the page shows the four user-selectable policies. Headline metrics are unweighted
means of 70 run-level observations per policy, not pooled packet rates.

A separate fresh live example runs each of the four policies for 120 × 0.2s steps.
It calls `LiveSession`, which reuses the canonical policies, LinkAdapter, and metrics.
No JavaScript simulation or separate metric implementation is used.

- Two routes: Alpha at 1 Mbps / 2 ms per hop; Beta at 2.5 Mbps / 12 ms per hop.
- One 1,000-byte packet flow; buffers are 64,000 bytes per directed link.
- Start at 0.35 Mbps; increase to 1.8 Mbps at 8 seconds.
- Disable the Source–Beta cable at 16 seconds; restore it at 20 seconds.
- Stop at 24 seconds with pending packets retained; no final drain.

Adaptive, trend, and learned each deliver 3,605 of 3,950 packets, with 338 dropped
and 7 pending. Static delivers 2,348, with 1,537 dropped and 65 pending. The adaptive
event times are initial at 0s, congestion reroute at 8.2s, forced repair at 16s, and
return to Beta at 20s. The event replay reads those recorded decisions. Goodput in
the temporal graph is cumulative over the growing cohort; it is not instantaneous.
The studio screenshot comes from a separate browser verification session and is
identified as such on the page.

## Reproduction and downloadable assets

Run `.venv/bin/python scripts/generate-results.py`, then build the frontend.
The launcher performs these steps automatically. Assets in `frontend/public/results/`
include `data.json`, `delivery.svg`, `latency.svg`, `traffic.svg`, `studio.jpg`,
`benchmark.csv`, and `audit.json`. Live data also goes to ignored
`artifacts/results-page-live.json`. SVGs are standalone, titled and described.
They can be exported without a plotting service or a browser screenshot.

## Startup behavior

`./start-studio.sh` works from any working directory. On macOS,
`Start SmartRoute.command` delegates to it for a double-click launch. The script
validates the port, checks dependencies/model compatibility, generates result assets,
and builds successfully before terminating listeners on the selected port.
It sends TERM, waits up to 3 seconds, then KILL to original listeners still holding
the port. If another process grabs the port or termination is denied, it fails with
a useful message. It does not kill processes on other ports or use broad name matching.
The default is 8765; override with `SMARTROUTE_PORT=9000 ./start-studio.sh`.

React and the Python API share that loopback-only port. The launcher stays in the
foreground; Ctrl+C stops the server. A running session is lost when its server is
restarted, while browser-saved network layouts remain available.
