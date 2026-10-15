"""Dashboard actions use the canonical engine, metrics and persistence."""

import os
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from smartroute.cli import POLICIES, make_policy
from smartroute.engine.sdk import SimulationEngine
from smartroute.serialization import canonical, digest, load_result

ROOT = Path(__file__).resolve().parents[3]
MODEL = ROOT / "models" / "selected"


def artifact_path(name):
    root = Path(os.environ.get("SMARTROUTE_ARTIFACT_DIR", ROOT / "artifacts")).resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Write path must stay inside the artifact directory")
    return path


def simulate(config, policy):
    engine = SimulationEngine()
    return engine.run(config, engine.make_workload(config), make_policy(policy, MODEL))


def compare(config):
    engine = SimulationEngine()
    workload = engine.make_workload(config)
    return [engine.run(config, workload, make_policy(policy, MODEL)) for policy in POLICIES]


def summary_frame(results):
    return pd.DataFrame(
        [
            {
                "policy": result.policy_name,
                **asdict(result.metrics),
                "normal_route_changes": result.metrics.route_changes
                - result.metrics.forced_route_changes,
                "trace_sha256": result.trace_sha256,
            }
            for result in results
        ]
    )


def telemetry_frame(result):
    return pd.DataFrame(
        [
            {
                "time_s": snap.time_s,
                **asdict(link),
                "service_utilization": link.busy_s / snap.interval_s,
            }
            for snap in result.snapshots
            for link in snap.links
        ]
    )


def forecast_frame(result):
    return pd.DataFrame([asdict(f) for d in result.decisions for f in d.decision.forecasts])


def export_json(result):
    return canonical(result).encode()


def import_result(data):
    if len(data) > 20_000_000:
        raise ValueError("Replay file exceeds 20 MB")
    path = artifact_path(f"imports/{digest(data.decode('utf-8'))}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return load_result(path)
