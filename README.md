# SmartRoute AI

A local laboratory for reproducible, prediction-assisted network routing. It includes
a **React network studio**, a SimPy packet engine, routing policies, a trained demand
forecaster and paired experiments. No account, API key or cloud service is needed.

## Open the React network studio

The studio runs at **http://127.0.0.1:8765** while its process is alive.
With the Python environment below installed and Node.js 24 available, start it from this folder:

```sh
./start-studio.sh
```

On macOS, you can also double-click **Start SmartRoute.command** in this folder.
The script checks the trained model, refreshes result graphs using real simulator
outputs, installs the locked frontend packages on first launch, and builds React.
It then stops listeners occupying **port 8765** (first gracefully, then forcibly if
necessary) and serves the app and local live API from one Python process.
Keep the terminal open; Ctrl+C stops the project. To choose another port:

```sh
SMARTROUTE_PORT=9000 ./start-studio.sh
```

Only the selected port is cleared; a process belonging to another user may require
you to stop it yourself. The Python environment must be installed once as described below.
The main frontend uses
React, TypeScript, Vite and React Flow. Streamlit is retained only as a legacy report viewer.

Drag devices from the library, connect their ports (or use the cable tool and click two
devices), then select a wire to set maximum traffic, latency and buffer size. Add a
traffic flow and press **Start simulation**. Traffic, capacity and link availability
can change live while queues and in-flight packets remain intact. Reset before editing
the topology or changing policies. IP labels annotate devices; the simulation uses source routes.

The included demo has a short 1 Mbps path through Core Alpha and a longer 2.5 Mbps
path through Core Beta. Start at 0.35 Mbps, then press **Stress test** to increase demand
to 1.8 Mbps. Watch the path change and inspect its reason in the event log. Disable an
active cable to trigger failover. Packet motion samples real wire-entry events, slowed
for visibility; the counters include every simulated packet.

Network layout/settings autosave in browser storage. Save/import network JSON for
portable topologies; export simulation data for packet outcomes and timestamped control edits.
See [React studio details](docs/REACT_STUDIO.md) for controls, API and live metric semantics.

## View project results

Choose **Results** in the navigation, or open **http://127.0.0.1:8765/#results**.
The page contains delivery and latency charts from the audited 350-run benchmark,
a scenario breakdown, a fresh 24-second traffic-spike/link-failure experiment,
clickable recorded routes, and an actual studio screenshot. Download individual
SVG graphs, the screenshot, the run-level CSV, the audit, or all page data.

The live example generates 3,950 packets under each policy: adaptive delivers
3,605 and static delivers 2,348 at 24 seconds. Pending packets are explicitly
reported; the live example has no final drain and is separate from the sealed benchmark.
Opening Results pauses an active studio session while preserving its layout and state.

To regenerate page assets without starting the service:

```sh
.venv/bin/python scripts/generate-results.py
cd frontend && npm run build
```

The generator checks benchmark headlines against all 350 run-level records and
checks packet conservation in every fresh live step. It does not retrain the model
or rerun the sealed benchmark. See [results page details](docs/RESULTS_PAGE.md).

For frontend development, run the Python service and Vite in separate terminals:

```sh
.venv/bin/python -m smartroute.web.server --port 8765
# Second terminal:
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to the local Python service. After frontend changes, rebuild and
reload the browser. After Python changes, restart the service. Live sessions last at
most five simulated minutes or 200,000 packets; reset to continue.

## Install from the lock

Python **3.12** and [uv](https://docs.astral.sh/uv/) are required for these commands.
Run from the repository root. `requirements.lock` pins the actually installed and tested
versions of all runtime/development dependencies, including SimPy 4.1.1 and the build tool.

```sh
uv venv --python python3.12 .venv
uv pip sync --python .venv/bin/python requirements.lock
uv pip install --python .venv/bin/python --no-deps --no-build-isolation -e .
source .venv/bin/activate
python -m pytest -q
python -m ruff check src tests
cd frontend
npm ci
npm test
npm run build
```

The model metadata verifies NumPy, scikit-learn, joblib, SimPy and NetworkX versions,
feature schema, source hash and artifact bytes before loading. If you change inference
or engine source, regenerate the model and affected experiment results.

## Command line

```sh
python -m smartroute.cli catalog
python -m smartroute.cli trace --topology diamond --scenario ramp --seed 0 --output artifacts/trace.json
python -m smartroute.cli run --topology diamond --scenario ramp --seed 0 --policy static --output artifacts/static.json
python -m smartroute.cli run --topology diamond --scenario ramp --seed 0 --policy reactive --trace artifacts/trace.json --output artifacts/reactive.json
python -m smartroute.cli run --topology small-mesh --scenario failure --policy predictive-learned --output artifacts/learned.json
```

Policies: `static`, `reactive`, `predictive-persistence`, `predictive-trend`,
`predictive-learned`. Overrides: `--load-multiplier 0.25..2` and `--event-time-s`
(capacity/failure presets). Use `--config path.json` for a fully expanded configuration;
this is mutually exclusive with topology/scenario presets. The catalog also ships
expanded configuration examples under `configs/examples/`.

## Reproduce the evidence

```sh
python -m smartroute.intelligence.train --train-config experiment_configs/train.json --validation-config experiment_configs/validation.json --output models/selected
python -m smartroute.experiments.run --suite validation-ablation --output artifacts/validation-ablation
python -m smartroute.experiments.run --suite smoke --output artifacts/smoke
python -m smartroute.experiments.run --suite full --model models/selected --output artifacts/final-benchmark
python -m smartroute.experiments.audit --manifest artifacts/final-benchmark/manifest.json
python -m smartroute.experiments.run --suite stress --output artifacts/stress
python -m smartroute.experiments.publish_report
```

Training creates 140 train and 42 validation workload families, each under static and
reactive routing. The sealed test has 70 families: seven scenarios × two topologies ×
five seeds. Each uses five policies: **350 paired test runs**. Stress and validation-only
no-hysteresis runs are reported separately. All scorer parameters remain the predeclared
shared defaults; model selection uses validation only. Suite reruns regenerate results
rather than resuming from unchecked cached files.

Large packet ledgers, datasets and run results live in ignored `artifacts/`.
Compact model artifacts and evidence summaries are retained in `models/` and
`docs/evidence/`. `SMARTROUTE_ARTIFACT_DIR` can change the dashboard's managed write root;
CLI output locations are explicit. Model loading accepts only trusted project model/artifact
directories. Replay uploads accept validated JSON, never executable model uploads.

Read [engine semantics](docs/ENGINE.md), [model card](docs/MODEL_CARD.md),
[measured results](docs/RESULTS.md), [demo steps](docs/DEMO.md) and
[implementation decisions](docs/DECISIONS.md). The original build pack is retained in
`docs/build/`; `starter/` remains untouched for provenance.
