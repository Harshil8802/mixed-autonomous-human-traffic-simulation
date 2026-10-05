"""Run the mixed-traffic model from the command line."""

import argparse
import csv
import json
from pathlib import Path

from .model import BrakingDisturbance, SimulationConfig, run_simulation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the mixed circular traffic model")
    parser.add_argument("--road-length", type=int, default=200)
    parser.add_argument("--vehicles", type=int, default=40)
    parser.add_argument("--max-speed", type=int, default=5)
    parser.add_argument("--human-slow-prob", type=float, default=0.2)
    parser.add_argument("--steps", type=int, default=800)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--csv", type=Path, help="Write per-step metrics to this CSV file")
    parser.add_argument("--av-share", type=float, default=0.0, help="Fraction of autonomous vehicles (0 to 1)")
    parser.add_argument(
        "--av-policy",
        choices=("reactive", "anticipatory"),
        default="reactive",
        help="Autonomous-vehicle controller (default: reactive)",
    )
    parser.add_argument(
        "--lanes",
        type=int,
        choices=(1, 2),
        default=1,
        help="Number of parallel circular lanes (default: 1)",
    )
    parser.add_argument(
        "--disturbance-start-step",
        type=int,
        help="Measurement step at which a controlled braking event begins",
    )
    parser.add_argument("--disturbance-duration", type=int, default=8)
    parser.add_argument("--disturbance-vehicle-id", type=int, default=0)
    parser.add_argument("--disturbance-speed-cap", type=int, default=0)
    args = parser.parse_args()

    config = SimulationConfig(
        road_length=args.road_length,
        num_vehicles=args.vehicles,
        max_speed=args.max_speed,
        human_slow_probability=args.human_slow_prob,
        av_share=args.av_share,
        seed=args.seed,
        av_policy=args.av_policy,
        lanes=args.lanes,
    )
    
    disturbance = (
        BrakingDisturbance(
            vehicle_id=args.disturbance_vehicle_id,
            start_step=args.disturbance_start_step,
            duration=args.disturbance_duration,
            speed_cap=args.disturbance_speed_cap,
        )
        if args.disturbance_start_step is not None
        else None
    )
    result = run_simulation(
        config,
        steps=args.steps,
        warmup=args.warmup,
        disturbance=disturbance,
    )
    
    if args.csv is not None:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as stream:
            # Fieldnames automatically pick up requested_av_share and realised_av_share per row
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
