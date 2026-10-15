import json
import shutil

import pytest

from smartroute.experiments.audit import audit
from smartroute.experiments.run import run_suite
from smartroute.intelligence.model_io import file_hash


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    directory = tmp_path_factory.mktemp("paired-smoke")
    run_suite("smoke", "models/selected", directory)
    return directory


def copy_smoke(smoke, tmp_path):
    target = tmp_path / "suite"
    shutil.copytree(smoke, target)
    path = target / "manifest.json"
    return path, json.loads(path.read_text())


def test_real_smoke_audited(smoke):
    report = audit(smoke / "manifest.json")
    assert report["runs"] == 10 and report["paired_traces"]


@pytest.mark.parametrize(
    "corruption", ["missing", "duplicate", "model", "failed", "trace", "metric", "schema"]
)
def test_audit_rejects_inconsistent_evidence(smoke, tmp_path, corruption):
    path, manifest = copy_smoke(smoke, tmp_path)
    entry = manifest["runs"][0]
    result_file = path.parent / entry["file"]
    if corruption == "missing":
        result_file.unlink()
    elif corruption == "duplicate":
        manifest["runs"].append(entry)
    elif corruption == "model":
        manifest["model_sha256"] = "invalid"
    elif corruption == "failed":
        entry["status"] = "failed"
    elif corruption == "trace":
        entry["trace_sha256"] = "0" * 64
    elif corruption in ("metric", "schema"):
        result = json.loads(result_file.read_text())
        if corruption == "metric":
            result["metrics"]["generated"] += 1
        else:
            result["schema_version"] = "99"
        result_file.write_text(json.dumps(result))
        entry["result_sha256"] = file_hash(result_file)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        audit(path)


def test_regeneration_replaces_stale_output(smoke, tmp_path):
    path, manifest = copy_smoke(smoke, tmp_path)
    manifest["runs"][0]["trace_sha256"] = "stale"
    path.write_text(json.dumps(manifest))
    run_suite("smoke", "models/selected", path.parent)
    assert audit(path)["status"] == "passed"
