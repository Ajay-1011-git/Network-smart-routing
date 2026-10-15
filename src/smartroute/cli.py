import argparse
import json
import sys
from pathlib import Path

from smartroute.baselines import ReactivePolicy, StaticPolicy
from smartroute.engine.sdk import SimulationEngine
from smartroute.engine.topology import SCENARIOS, TOPOLOGIES, catalog_config, override_config
from smartroute.serialization import (
    atomic_json,
    load_config,
    load_workload,
    save_result,
    save_workload,
)

POLICIES = (
    "static",
    "reactive",
    "predictive-persistence",
    "predictive-trend",
    "predictive-learned",
)


def make_policy(name, model="models/selected", **scorer):
    if name == "static":
        return StaticPolicy()
    if name == "reactive":
        return ReactivePolicy(**scorer)
    if name in POLICIES:
        from smartroute.intelligence.policy import PredictivePolicy

        return PredictivePolicy(name.removeprefix("predictive-"), model, **scorer)
    raise ValueError(f"Unknown policy {name}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="SmartRoute reproducible routing laboratory")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog")
    for name in ("trace", "run"):
        command = sub.add_parser(name)
        command.add_argument("--topology", choices=TOPOLOGIES)
        command.add_argument("--scenario", choices=SCENARIOS)
        command.add_argument("--seed", type=int, default=0)
        command.add_argument("--config")
        command.add_argument("--load-multiplier", type=float, default=1.0)
        command.add_argument("--event-time-s", type=float)
        command.add_argument("--output", required=True)
        if name == "run":
            command.add_argument("--policy", choices=POLICIES, default="reactive")
            command.add_argument("--model", default="models/selected")
            command.add_argument("--trace")
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            print(
                json.dumps({"topologies": TOPOLOGIES, "scenarios": SCENARIOS, "policies": POLICIES})
            )
            return 0
        if args.config:
            if args.topology or args.scenario:
                raise ValueError("Use either --config or preset topology/scenario")
            config = override_config(
                load_config(args.config), args.load_multiplier, args.event_time_s
            )
        else:
            config = catalog_config(
                args.topology or "diamond",
                args.scenario or "ramp",
                args.seed,
                args.load_multiplier,
                args.event_time_s,
            )
        engine = SimulationEngine()
        workload = (
            load_workload(args.trace)
            if getattr(args, "trace", None)
            else engine.make_workload(config)
        )
        if args.command == "trace":
            save_workload(workload, args.output)
            print(f"{len(workload.packets)} packets; trace {workload.trace_sha256}")
        else:
            result = engine.run(config, workload, make_policy(args.policy, args.model))
            save_result(result, args.output)
            from dataclasses import asdict

            print(json.dumps({"trace": result.trace_sha256, "metrics": asdict(result.metrics)}))
        return 0
    except Exception as exc:
        if getattr(args, "output", None):
            atomic_json(
                {"status": "failed", "error": str(exc), "type": type(exc).__name__},
                Path(str(args.output) + ".failure.json"),
            )
        print(f"SmartRoute: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
