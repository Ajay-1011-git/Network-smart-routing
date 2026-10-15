"""Publish audited measurements and a fresh live experiment as local page assets.

Run from any directory with .venv/bin/python scripts/generate-results.py.
The simulator owns all metrics. This script formats its outputs for presentation.
"""

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from statistics import mean

from smartroute.web.live import LiveSession

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/evidence"
OUTPUT = ROOT / "frontend/public/results"
POLICIES = ["static", "reactive", "predictive-trend", "predictive-learned"]
LABELS = ["Static", "Adaptive", "Predictive · trend", "Predictive · learned"]
COLORS = ["#777786", "#8b8bfe", "#7fd579", "#d896ff"]


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def svg_start(title, description, width=900, height=360):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
        '<rect width="100%" height="100%" fill="#161616"/>',
        '<g font-family="Arial, sans-serif" font-size="14" fill="#b1b1bc">',
    ]


def bar_chart(report, metric, scale, maximum, unit, title):
    parts = svg_start(title, "Mean of 70 paired workload runs per policy. " + unit)
    for i in range(5):
        value = maximum * i / 4
        x = 220 + value / maximum * 570
        parts.append(f'<path d="M{x} 38V290" stroke="#303036" stroke-dasharray="3 5"/>')
        parts.append(f'<text x="{x}" y="318" text-anchor="middle">{value:g}{unit}</text>')
    for i, (policy, label, color) in enumerate(zip(POLICIES, LABELS, COLORS)):
        value = report["by_policy"][policy][metric] * scale
        y = 63 + i * 61
        parts.extend([
            f'<text x="197" y="{y + 20}" text-anchor="end">{escape(label)}</text>',
            f'<rect x="220" y="{y}" width="{value / maximum * 570}" height="29" '
            f'fill="{color}" rx="1"/>',
            f'<text x="{232 + value / maximum * 570}" y="{y + 20}" '
            f'fill="#eaeaea">{value:.2f}</text>',
        ])
    parts.append('</g></svg>')
    return "\n".join(parts)


def live_network(policy):
    return {
        "policy": policy,
        "nodes": [
            {"id": node, "kind": "router", "label": node, "position": {"x": 0, "y": 0}}
            for node in ("Source", "Alpha", "Beta", "Destination")
        ],
        "connections": [
            {"id": id_, "source": source, "target": target, "capacity_mbps": capacity,
             "latency_ms": delay, "buffer_bytes": 64000, "up": True}
            for id_, source, target, capacity, delay in [
                ("sa", "Source", "Alpha", 1, 2),
                ("at", "Alpha", "Destination", 1, 2),
                ("sb", "Source", "Beta", 2.5, 12),
                ("bt", "Beta", "Destination", 2.5, 12),
            ]
        ],
        "flows": [{"id": "f", "source": "Source", "target": "Destination",
                   "rate_mbps": 0.35, "packet_bytes": 1000}],
    }


def run_live_example():
    runs = {}
    for policy in POLICIES:
        session = LiveSession(live_network(policy))
        samples = []
        for tick in range(120):
            changes = {}
            if tick == 40:
                changes = {"rates": {"f": 1.8}}
            if tick == 80:
                changes = {"connections": {"sb": {"up": False}}}
            if tick == 100:
                changes = {"connections": {"sb": {"up": True}}}
            state = session.step(changes)
            metrics = state["metrics"]
            assert metrics["generated"] == sum(metrics[k] for k in ("delivered", "dropped", "pending"))
            samples.append({"time_s": state["time_s"], "demand_mbps": session.rates["f"] / 1e6,
                            "goodput_mbps": metrics["throughput_bps"] / 1e6})
        runs[policy] = {"samples": samples, "metrics": state["metrics"],
                        "events": list(state["events"])}
    assert runs["reactive"]["metrics"]["route_changes"] >= 2
    return {
        "duration_s": 24, "interval_s": 0.2,
        "semantics": "Live generation cohort [0,24s); no final drain. Goodput is cumulative.",
        "controls": [{"time_s": 8, "label": "Traffic rises", "detail": "0.35 → 1.8 Mbps"},
                     {"time_s": 16, "label": "Beta link fails", "detail": "Alternative path unavailable"},
                     {"time_s": 20, "label": "Link restored", "detail": "Beta path available again"}],
        "network": live_network("reactive"), "runs": runs,
    }


def trace_chart(live):
    parts = svg_start("Traffic spike and link failure", "Demand compared with cumulative goodput "
                      "for adaptive and static routing during a fresh 24-second experiment.", height=390)
    def x(time):
        return 68 + time / 24 * 770

    def y(value):
        return 287 - value / 2 * 234
    for value in (0, 0.5, 1, 1.5, 2):
        parts.append(f'<path d="M68 {y(value)}H838" stroke="#303036"/>')
        parts.append(f'<text x="54" y="{y(value) + 5}" text-anchor="end">{value:g}</text>')
    for t in range(0, 25, 4):
        parts.append(f'<text x="{x(t)}" y="313" text-anchor="middle">{t}s</text>')
    for t, label in ((8, "Traffic ↑"), (16, "Link down"), (20, "Restored")):
        parts.append(f'<path d="M{x(t)} 35V287" stroke="#656578" stroke-dasharray="4 5"/>')
        parts.append(f'<text x="{x(t) + 7}" y="28" font-size="12">{label}</text>')
    for policy, key, color, dash in [("reactive", "demand_mbps", "#eaeaea", 'stroke-dasharray="5 5"'),
                                     ("reactive", "goodput_mbps", "#8b8bfe", ""),
                                     ("static", "goodput_mbps", "#7b7b86", "")]:
        points = " ".join(f'{x(s["time_s"]):.2f},{y(s[key]):.2f}'
                          for s in live["runs"][policy]["samples"])
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" '
                     f'stroke-width="2.5" {dash}/>')
    parts.extend(['<text x="68" y="353" fill="#eaeaea">— — Demand</text>',
                  '<text x="260" y="353" fill="#8b8bfe">━ Adaptive goodput</text>',
                  '<text x="515" y="353" fill="#9292a1">━ Static goodput</text>',
                  '<text x="68" y="20" font-size="12">Mbps</text>', '</g></svg>'])
    return "\n".join(parts)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = json.loads((EVIDENCE / "report.json").read_text())
    audit = json.loads((EVIDENCE / "benchmark-audit.json").read_text())
    metadata = json.loads((ROOT / "models/selected/metadata.json").read_text())
    rows = list(csv.DictReader((EVIDENCE / "summary.csv").open()))
    assert report["status"] == "complete" and report["failed_runs"] == 0
    assert audit["status"] == "passed" and audit["paired_traces"] and audit["split_disjoint"]
    assert len(rows) == report["completed_runs"] == audit["runs"] == 350
    assert metadata["source_hash"] == audit["source_hash"]
    # Validate published headlines against underlying run-level data.
    for policy in report["by_policy"]:
        group = [row for row in rows if row["policy"] == policy]
        assert len(group) == 70
        for metric in ("delivery_ratio", "mean_latency_s", "throughput_bps"):
            actual = mean(float(row[metric]) for row in group)
            assert abs(actual - report["by_policy"][policy][metric]) < 1e-6
    scenarios = defaultdict(dict)
    for scenario in sorted({row["scenario"] for row in rows}):
        for policy in POLICIES:
            group = [row for row in rows if row["scenario"] == scenario and row["policy"] == policy]
            scenarios[scenario][policy] = mean(float(row["delivery_ratio"]) for row in group)
    live = run_live_example()
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_version": metadata["experiment_version"],
        "benchmark": {"runs": 350, "families": 70, "scenarios": 7, "topologies": 2,
                      "seeds_per_topology": 5, "policies": 5, "failed": 0,
                      "report": report["by_policy"], "by_scenario": scenarios,
                      "source_sha256": audit["source_hash"],
                      "summary_sha256": hashlib.sha256((EVIDENCE / "summary.csv").read_bytes()).hexdigest()},
        "live": live,
    }
    write_json(OUTPUT / "data.json", data)
    (OUTPUT / "delivery.svg").write_text(bar_chart(report, "delivery_ratio", 100, 100, "%", "Packet delivery"))
    (OUTPUT / "latency.svg").write_text(bar_chart(report, "mean_latency_s", 1000, 100, " ms", "Mean packet latency"))
    (OUTPUT / "traffic.svg").write_text(trace_chart(live))
    for source, target in [("summary.csv", "benchmark.csv"), ("benchmark-audit.json", "audit.json"),
                            ("react-studio.jpg", "studio.jpg")]:
        shutil.copyfile(EVIDENCE / source, OUTPUT / target)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    write_json(ROOT / "artifacts" / "results-page-live.json", live)
    print(f"Results ready: {len(rows)} audited runs + four fresh 24-second live experiments.")


if __name__ == "__main__":
    main()
