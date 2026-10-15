"""Only load trusted app-generated models; verify bytes before unpickling."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import joblib

from smartroute.intelligence.features import FEATURE_HASH
from smartroute.serialization import atomic_json, digest

ROOT = Path(__file__).resolve().parents[3]


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hash():
    root = ROOT / "src" / "smartroute"
    return digest(
        {
            str(p.relative_to(root)): file_hash(p)
            for p in sorted(root.rglob("*.py"))
            if "dashboard" not in p.parts and "experiments" not in p.parts and p.name != "cli.py"
        }
    )


def dependencies():
    return {
        name: version(name) for name in ("numpy", "scikit-learn", "joblib", "simpy", "networkx")
    }


def trusted_directory(directory):
    directory = Path(directory).resolve()
    import os

    roots = [
        (ROOT / "models").resolve(),
        Path(os.environ.get("SMARTROUTE_ARTIFACT_DIR", ROOT / "artifacts")).resolve(),
    ]
    if not any(directory.is_relative_to(root) for root in roots):
        raise ValueError("Model must be in the application's models or artifact directory")
    return directory


def save_model(estimator, directory, metadata):
    directory = trusted_directory(directory)
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(estimator, directory / "model.joblib")
    metadata = {
        **metadata,
        "schema_version": "1.0",
        "feature_hash": FEATURE_HASH,
        "dependencies": dependencies(),
        "source_hash": source_hash(),
        "model_sha256": file_hash(directory / "model.joblib"),
    }
    atomic_json(metadata, directory / "metadata.json")
    return metadata


def load_model(directory):
    directory = trusted_directory(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    if (
        metadata.get("schema_version") != "1.0"
        or metadata.get("feature_hash") != FEATURE_HASH
        or metadata.get("dependencies") != dependencies()
        or metadata.get("source_hash") != source_hash()
        or metadata.get("model_sha256") != file_hash(directory / "model.joblib")
    ):
        raise ValueError("Model metadata/dependency/source/hash mismatch; retrain this version")
    return joblib.load(directory / "model.joblib"), metadata
