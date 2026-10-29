"""Audit the extended held-out test and publish its compact evidence."""

import json
import shutil
from pathlib import Path

import pandas as pd

from smartroute.experiments.audit import audit
from smartroute.experiments.statistics import paired_statistics
from smartroute.intelligence.model_io import file_hash
from smartroute.serialization import atomic_json


def main():
    root = Path("artifacts/extended-test")
    evidence = Path("docs/evidence/extended-test")
    evidence.mkdir(parents=True, exist_ok=True)
    checked = audit(root / "manifest.json")
    manifest = json.loads((root / "manifest.json").read_text())
    atomic_json(
        {
            **checked,
            "suite": manifest["suite"],
            "seeds": manifest["spec"]["seeds"],
            "manifest_path": str(root / "manifest.json"),
            "manifest_sha256": file_hash(root / "manifest.json"),
            "source_hash": manifest["source_hash"],
            "model_sha256": manifest["model_sha256"],
            "freeze_sha256": manifest["freeze_sha256"],
            "benchmark_duration_s": manifest["duration_s"],
            "environment": manifest["environment"],
        },
        evidence / "audit.json",
    )
    for name in ("summary.csv", "aggregate.csv", "report.json"):
        shutil.copyfile(root / name, evidence / name)
    atomic_json(paired_statistics(pd.read_csv(root / "summary.csv")), evidence / "statistics.json")
    print(json.dumps(checked))


if __name__ == "__main__":
    main()
