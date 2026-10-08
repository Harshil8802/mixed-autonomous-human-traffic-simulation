"""Run the small density-by-AV-share pilot used for Checkpoint 2."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from traffic_sim import SimulationConfig, run_simulation


DEFAULT_OUTPUT = Path("results/checkpoint2-pilot.csv")
VEHICLE_COUNTS = (20, 40, 60)
AV_SHARES = (0.0, 0.5, 1.0)


def parse_seeds(value: str) -> list[int]:
    seeds = [int(item.strip()) for item in value.split(",") if item.strip()]
    if not seeds:
        raise argparse.ArgumentTypeError("provide at least one integer seed")
    return seeds


def run_pilot(seeds: list[int]) -> list[dict]:
    rows = []
    for num_vehicles in VEHICLE_COUNTS:
        for av_share in AV_SHARES:
            for seed in seeds:
                config = SimulationConfig(
                    road_length=200,
                    num_vehicles=num_vehicles,
                    max_speed=5,
                    human_slow_probability=0.2,
                    av_share=av_share,
                    seed=seed,
                )
                result = run_simulation(config, warmup=200, steps=800)
                rows.append(
                    {
                        "road_length": config.road_length,
                        "num_vehicles": num_vehicles,
                        "density": num_vehicles / config.road_length,
                        "requested_av_share": av_share,
                        "realised_av_share": result["realised_av_share"],
                        "seed": seed,
                        "warmup": result["warmup"],
                        "steps": result["steps"],
                        **result["summary"],
                    }
                )
    return rows


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def print_table(rows: list[dict]) -> None:
    print("| Density | Vehicles | AV share | Seed | Mean speed | Stopped | Speed SD |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row['density']:.2f} | {row['num_vehicles']} | "
            f"{row['realised_av_share']:.0%} | {row['seed']} | "
            f"{row['mean_speed']:.3f} | {row['stopped_fraction']:.2%} | "
            f"{row['speed_std']:.3f} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=parse_seeds,
        default=[7],
        help="Comma-separated integer seeds (default: 7)",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = run_pilot(args.seeds)
    write_csv(rows, args.output)
    print_table(rows)
    print(f"\nWrote {len(rows)} runs to {args.output}")


if __name__ == "__main__":
    main()
