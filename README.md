# SmartRoute AI

A local laboratory for reproducible, prediction-assisted network routing. It includes
a SimPy packet engine, five routing policies, a trained demand forecaster, paired
experiments and a Streamlit/Plotly dashboard. No account, API key or cloud service is needed.

## Open the dashboard

The development instance runs at **http://127.0.0.1:8501** while its process is alive.
To start it again from this folder:

```sh
source .venv/bin/activate
python -m streamlit run src/smartroute/dashboard/app.py --server.address 127.0.0.1
```

Choose a scenario and press **Run simulation**. The replay, forecasts, explanations,
comparison and export tabs all use real SDK results. Controls do not run an experiment
until you press Run or Compare. Predictive learned mode uses the included trusted local
model in `models/selected`; missing/incompatible artifacts produce a visible error.

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
