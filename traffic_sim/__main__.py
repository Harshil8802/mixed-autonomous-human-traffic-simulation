"""Run the human-only traffic baseline from the command line."""

import argparse
import csv
import json
from pathlib import Path

from .model import SimulationConfig, run_simulation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the human-only circular traffic model")
    parser.add_argument("--road-length", type=int, default=200)
    parser.add_argument("--vehicles", type=int, default=40)
    parser.add_argument("--max-speed", type=int, default=5)
    parser.add_argument("--human-slow-prob", type=float, default=0.2)
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--csv", type=Path, help="Write per-step metrics to this CSV file")
    args = parser.parse_args()

    config = SimulationConfig(
        road_length=args.road_length,
        num_vehicles=args.vehicles,
        max_speed=args.max_speed,
        human_slow_probability=args.human_slow_prob,
        seed=args.seed,
    )
    result = run_simulation(config, steps=args.steps, warmup=args.warmup)
    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=result["per_step"][0].keys())
            writer.writeheader()
            writer.writerows(result["per_step"])

    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "per_step"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
