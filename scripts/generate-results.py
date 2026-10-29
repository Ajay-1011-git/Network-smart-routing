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

import pandas as pd

from smartroute.experiments.statistics import paired_statistics, version_effects
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


def bar_chart(by_policy, metric, scale, maximum, unit, title, runs, intervals=None):
    parts = svg_start(title, f"Mean of {runs} paired workload runs per policy. " + unit
                      + (" Whiskers show paired seed-block bootstrap 95% intervals." if intervals else ""))
    for i in range(5):
        value = maximum * i / 4
        x = 220 + value / maximum * 570
        parts.append(f'<path d="M{x} 38V290" stroke="#303036" stroke-dasharray="3 5"/>')
        parts.append(f'<text x="{x}" y="318" text-anchor="middle">{value:g}{unit}</text>')
    for i, (policy, label, color) in enumerate(zip(POLICIES, LABELS, COLORS)):
        value = by_policy[policy][metric] * scale
        y = 63 + i * 61
        label_x = 232 + value / maximum * 570
        parts.extend([
            f'<text x="197" y="{y + 20}" text-anchor="end">{escape(label)}</text>',
            f'<rect x="220" y="{y}" width="{value / maximum * 570}" height="29" '
            f'fill="{color}" rx="1"/>',
        ])
        if intervals:
            low, high = (v * scale / maximum * 570 + 220 for v in intervals[policy]["ci95"])
            parts.append(f'<path d="M{low:.2f} {y + 14.5}H{high:.2f}M{low:.2f} {y + 7}V{y + 22}'
                         f'M{high:.2f} {y + 7}V{y + 22}" stroke="#eaeaea" stroke-width="1.6"/>')
            label_x = max(label_x, high + 12)
        parts.append(f'<text x="{label_x:.2f}" y="{y + 20}" fill="#eaeaea">{value:.2f}</text>')
    parts.append('</g></svg>')
    return "\n".join(parts)


def forest_chart(statistics):
    rows = statistics["comparisons"]
    height = 90 + 52 * len(rows)
    parts = svg_start("Paired delivery differences",
                      "Mean candidate-minus-baseline delivery difference in percentage points, with "
                      "paired seed-block bootstrap 95% intervals. Intervals entirely right of zero "
                      "favor the candidate.", height=height)
    values = [v * 100 for r in rows for v in r["ci95"]]
    low, high = min(min(values), 0) - 0.5, max(max(values), 0) + 0.5
    def x(value):
        return 330 + (value - low) / (high - low) * 520
    step = 1 if high - low <= 8 else 2
    for tick in range(int(low // step) * step, int(high) + 1, step):
        if low <= tick <= high:
            parts.append(f'<path d="M{x(tick):.2f} 40V{height - 50}" stroke="#303036" '
                         f'stroke-dasharray="3 5"/>')
            parts.append(f'<text x="{x(tick):.2f}" y="{height - 28}" text-anchor="middle">'
                         f'{tick:+g} pp</text>'.replace('+0 pp', '0 pp'))
    parts.append(f'<path d="M{x(0):.2f} 34V{height - 46}" stroke="#eaeaea" stroke-width="1.2"/>')
    names = dict(zip(POLICIES, LABELS))
    for i, row in enumerate(rows):
        y = 62 + i * 52
        color = {"higher": "#7fd579", "lower": "#f0a3a3"}.get(row["conclusion"], "#b1b1bc")
        a, b = (v * 100 for v in row["ci95"])
        mean = row["mean_delta"] * 100
        parts.extend([
            f'<text x="312" y="{y + 5}" text-anchor="end" fill="#eaeaea">'
            f'{escape(names[row["candidate"]])} vs {escape(names[row["baseline"]])}</text>',
            f'<path d="M{x(a):.2f} {y}H{x(b):.2f}" stroke="{color}" stroke-width="2.4"/>',
            f'<rect x="{x(mean) - 5:.2f}" y="{y - 5}" width="10" height="10" fill="{color}"/>',
            f'<text x="312" y="{y + 22}" text-anchor="end" font-size="11">'
            f'{mean:+.2f} pp [{a:+.2f}, {b:+.2f}] · {row["better_runs"]}/{row["equal_runs"]}/'
            f'{row["worse_runs"]} better/equal/worse</text>',
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


def scenario_means(rows):
    scenarios = defaultdict(dict)
    for scenario in sorted({row["scenario"] for row in rows}):
        for policy in POLICIES:
            group = [row for row in rows if row["scenario"] == scenario and row["policy"] == policy]
            scenarios[scenario][policy] = mean(float(row["delivery_ratio"]) for row in group)
    return scenarios


def check_headlines(report, rows, runs_per_policy):
    # Validate published headlines against underlying run-level data.
    for policy in report["by_policy"]:
        group = [row for row in rows if row["policy"] == policy]
        assert len(group) == runs_per_policy
        for metric in ("delivery_ratio", "mean_latency_s", "throughput_bps"):
            actual = mean(float(row[metric]) for row in group)
            assert abs(actual - report["by_policy"][policy][metric]) < 1e-6


def damping_chart(effects):
    parts = svg_start("Route changes before and after flap damping",
                      "Mean route changes per run on the same 3,500 held-out workloads, before (v1.3) "
                      "and after (v1.4) flap damping. Whiskers show the paired 95% interval of the change.")
    maximum = 25
    for i in range(6):
        value = maximum * i / 5
        x = 220 + value / maximum * 570
        parts.append(f'<path d="M{x} 38V290" stroke="#303036" stroke-dasharray="3 5"/>')
        parts.append(f'<text x="{x}" y="318" text-anchor="middle">{value:g}</text>')
    for i, (policy, label, color) in enumerate(zip(POLICIES, LABELS, COLORS)):
        change = effects[policy]["route_changes"]
        y = 52 + i * 61
        before, after = change["before"], change["after"]
        parts.extend([
            f'<text x="197" y="{y + 22}" text-anchor="end">{escape(label)}</text>',
            f'<rect x="220" y="{y}" width="{before / maximum * 570:.2f}" height="15" fill="#3a3a46"/>',
            f'<text x="{228 + before / maximum * 570:.2f}" y="{y + 12}" font-size="12">{before:.1f} before</text>',
            f'<rect x="220" y="{y + 18}" width="{after / maximum * 570:.2f}" height="15" fill="{color}"/>',
            f'<text x="{228 + after / maximum * 570:.2f}" y="{y + 30}" font-size="12" fill="#eaeaea">{after:.1f} after</text>',
        ])
    parts.append('<text x="220" y="345" font-size="12">Route changes per run</text></g></svg>')
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
    check_headlines(report, rows, 70)

    extended = EVIDENCE / "extended-test"
    ext_report = json.loads((extended / "report.json").read_text())
    ext_audit = json.loads((extended / "audit.json").read_text())
    ext_stats = json.loads((extended / "statistics.json").read_text())
    ext_rows = list(csv.DictReader((extended / "summary.csv").open()))
    assert ext_report["status"] == "complete" and ext_report["failed_runs"] == 0
    assert ext_audit["status"] == "passed" and ext_audit["paired_traces"]
    assert ext_audit["split_disjoint"] and ext_audit["suite"] == "extended-test"
    assert len(ext_rows) == ext_report["completed_runs"] == ext_audit["runs"] == 3500
    assert ext_audit["source_hash"] == metadata["source_hash"]
    assert ext_audit["model_sha256"] == metadata["model_sha256"]
    check_headlines(ext_report, ext_rows, 700)
    # The published intervals must be exactly reproducible from the run-level rows.
    assert paired_statistics(pd.read_csv(extended / "summary.csv")) == ext_stats
    for policy, values in ext_stats["by_policy"].items():
        assert abs(values["mean"] - ext_report["by_policy"][policy]["delivery_ratio"]) < 1e-9
    # Before/after flap damping on identical held-out workloads (v1.3 evidence is kept).
    before_dir = EVIDENCE / "v1.3/extended-test"
    before_audit = json.loads((before_dir / "audit.json").read_text())
    assert before_audit["status"] == "passed" and before_audit["runs"] == 3500
    assert before_audit["seeds"] == ext_audit["seeds"]
    before_rows = pd.read_csv(before_dir / "summary.csv")
    after_rows = pd.read_csv(extended / "summary.csv")
    assert (before_rows.groupby(["topology", "scenario", "seed"]).ngroups
            == after_rows.groupby(["topology", "scenario", "seed"]).ngroups == 700)
    effects = version_effects(before_rows, after_rows)
    static = effects["static"]["delivery_ratio"]
    assert static["mean_delta"] == 0 and static["ci95"] == [0, 0], "Static must be unaffected"
    damping = {key: value for key, value in metadata["scorer"].items() if key.startswith("flap_")}

    live = run_live_example()
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment_version": metadata["experiment_version"],
        "benchmark": {"runs": 350, "families": 70, "scenarios": 7, "topologies": 2,
                      "seeds_per_topology": 5, "policies": 5, "failed": 0,
                      "report": report["by_policy"], "by_scenario": scenario_means(rows),
                      "source_sha256": audit["source_hash"],
                      "summary_sha256": hashlib.sha256((EVIDENCE / "summary.csv").read_bytes()).hexdigest()},
        "extended": {"runs": 3500, "families": 700, "scenarios": 7, "topologies": 2,
                     "seeds": len(ext_audit["seeds"]), "seed_range": [min(ext_audit["seeds"]), max(ext_audit["seeds"])],
                     "policies": 5, "failed": 0, "report": ext_report["by_policy"],
                     "by_scenario": scenario_means(ext_rows), "statistics": ext_stats,
                     "source_sha256": ext_audit["source_hash"],
                     "summary_sha256": hashlib.sha256((extended / "summary.csv").read_bytes()).hexdigest()},
        "damping": {"parameters": damping, "before_version": "1.3", "effects": effects},
        "live": live,
    }
    # Keep the previous timestamp when nothing measured changed, so launching the
    # studio does not dirty tracked files with an identical deterministic rerun.
    previous = OUTPUT / "data.json"
    if previous.is_file():
        old = json.loads(previous.read_text())
        if {**old, "generated_at": None} == {**data, "generated_at": None}:
            data["generated_at"] = old["generated_at"]
    write_json(OUTPUT / "data.json", data)
    by_policy = ext_report["by_policy"]
    (OUTPUT / "delivery.svg").write_text(bar_chart(by_policy, "delivery_ratio", 100, 100, "%", "Packet delivery",
                                                   700, ext_stats["by_policy"]))
    (OUTPUT / "latency.svg").write_text(bar_chart(by_policy, "mean_latency_s", 1000, 100, " ms",
                                                  "Mean packet latency", 700))
    (OUTPUT / "paired.svg").write_text(forest_chart(ext_stats))
    (OUTPUT / "damping.svg").write_text(damping_chart(effects))
    (OUTPUT / "traffic.svg").write_text(trace_chart(live))
    for source, target in [("extended-test/summary.csv", "benchmark.csv"),
                           ("summary.csv", "benchmark-sealed.csv"),
                           ("extended-test/audit.json", "audit.json"),
                           ("benchmark-audit.json", "audit-sealed.json"),
                           ("extended-test/statistics.json", "statistics.json"),
                           ("react-studio.jpg", "studio.jpg")]:
        shutil.copyfile(EVIDENCE / source, OUTPUT / target)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    write_json(ROOT / "artifacts" / "results-page-live.json", live)
    print(f"Results ready: {len(ext_rows)} + {len(rows)} audited runs + four fresh 24-second live experiments.")


if __name__ == "__main__":
    main()
