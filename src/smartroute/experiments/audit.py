"""Independent matrix, file, pairing, split, hash and accounting audit."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from smartroute.cli import POLICIES
from smartroute.contracts import TracePacket
from smartroute.engine.workload import trace_digest
from smartroute.intelligence.dataset import split_manifest
from smartroute.intelligence.model_io import file_hash, load_model, source_hash
from smartroute.serialization import digest, load_result


def audit(path):
    path = Path(path)
    manifest = json.loads(path.read_text())

    def require(test, reason):
        if not test:
            raise ValueError(reason)

    require(
        manifest["schema_version"] == "1.0" and manifest["status"] == "complete",
        "Incomplete/invalid manifest",
    )
    _, metadata = load_model(manifest["model_path"])
    require(manifest["source_hash"] == source_hash(), "Source version mismatch")
    require(manifest["model_sha256"] == metadata["model_sha256"], "Model version mismatch")
    require(
        manifest["freeze_sha256"] == file_hash(Path(manifest["model_path"]) / "freeze.json"),
        "Freeze changed",
    )
    require(manifest["split_hashes"] == metadata["split_hashes"], "Split hashes changed")
    split = split_manifest(manifest["spec"])
    require(
        sorted(split["families"]) == manifest["expected_families"], "Family specification changed"
    )
    groups = [set(m["families"]) for m in metadata["split_manifests"]]
    require(not any(groups[i] & groups[j] for i in range(3) for j in range(i)), "Split overlap")
    if manifest["suite"] == "full":
        require(manifest["expected_runs"] == 350, "Full matrix must contain 350 runs")
        require(digest(split) == metadata["split_hashes"][2], "Sealed test assignments changed")
    policies = POLICIES if manifest["suite"] != "validation-ablation" else POLICIES[1:]
    variants = (
        ("default", "no-hysteresis") if manifest["suite"] == "validation-ablation" else ("default",)
    )
    expected = {
        (family, policy, variant)
        for family in split["families"]
        for policy in policies
        for variant in variants
    }
    actual, traces = set(), {}
    for entry in manifest["runs"]:
        key = entry["family_id"], entry["policy"], entry["variant"]
        require(key not in actual, "Duplicate run")
        actual.add(key)
        require(entry["status"] == "complete", f"Failed run: {entry['key']}")
        file = (path.parent / entry["file"]).resolve()
        require(
            file.is_relative_to(path.parent.resolve()), "Result file escapes manifest directory"
        )
        require(
            file.is_file() and file_hash(file) == entry["result_sha256"],
            "Missing/modified run file",
        )
        result = load_result(file)
        require(
            result.config_sha256 == entry["config_sha256"] == entry["family_id"], "Config mismatch"
        )
        require(result.policy_name == entry["policy"], "Policy mismatch")
        require(asdict(result.metrics) == entry["metrics"], "Metric summary mismatch")
        packets = tuple(
            TracePacket(p.packet_id, p.flow_id, p.generated_s, p.size_bytes) for p in result.packets
        )
        require(
            trace_digest(packets, result.config.events)
            == result.trace_sha256
            == entry["trace_sha256"],
            "Trace mismatch",
        )
        require(entry["model_sha256"] == metadata["model_sha256"], "Run model mismatch")
        previous = traces.setdefault(entry["family_id"], result.trace_sha256)
        require(previous == result.trace_sha256, "Paired policies used different traces")
        if entry["scenario"] in ("capacity", "failure"):
            require(len(entry["event_summary"]) == 2, "Scenario lacks required events")
    require(
        actual == expected and len(actual) == manifest["expected_runs"],
        "Missing/unexpected workload-policy pairs",
    )
    return {
        "status": "passed",
        "runs": len(actual),
        "families": len(traces),
        "paired_traces": True,
        "split_disjoint": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.manifest)))


if __name__ == "__main__":
    main()
