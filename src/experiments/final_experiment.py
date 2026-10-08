"""Run and aggregate the repeated-seed mixed-traffic experiment."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev
from typing import Iterable

from traffic_sim import SimulationConfig, run_simulation


DEFAULT_RAW_OUTPUT = Path("results/final-runs.csv")
DEFAULT_SUMMARY_OUTPUT = Path("results/final-summary.csv")
ROAD_LENGTH = 200
VEHICLE_COUNTS = (20, 40, 60)
AV_SHARES = (0.0, 0.10, 0.25, 0.50, 0.75, 1.0)
DEFAULT_SEEDS = tuple(range(1, 21))


def parse_seeds(value: str) -> list[int]:
    """Parse comma-separated integers and inclusive ranges such as ``1-20``."""

    seeds: list[int] = []
    try:
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start_text, end_text = part.split("-", maxsplit=1)
                start, end = int(start_text), int(end_text)
                if end < start:
                    raise ValueError("seed range must be ascending")
                seeds.extend(range(start, end + 1))
            else:
                seeds.append(int(part))
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "seeds must be comma-separated integers or ascending ranges"
        ) from error

    seeds = list(dict.fromkeys(seeds))
    if not seeds:
        raise argparse.ArgumentTypeError("provide at least one seed")
    return seeds


def run_experiment(
    seeds: Iterable[int],
    *,
    road_length: int = ROAD_LENGTH,
    vehicle_counts: Iterable[int] = VEHICLE_COUNTS,
    av_shares: Iterable[float] = AV_SHARES,
    max_speed: int = 5,
    human_slow_probability: float = 0.2,
    warmup: int = 200,
    steps: int = 800,
) -> list[dict]:
    """Run every density-by-AV-share-by-seed condition."""

    seed_values = tuple(seeds)
    if not seed_values:
        raise ValueError("at least one seed is required")

    rows = []
    for num_vehicles in vehicle_counts:
        for requested_av_share in av_shares:
            for seed in seed_values:
                config = SimulationConfig(
                    road_length=road_length,
                    num_vehicles=num_vehicles,
                    max_speed=max_speed,
                    human_slow_probability=human_slow_probability,
                    av_share=requested_av_share,
                    seed=seed,
                )
                result = run_simulation(config, warmup=warmup, steps=steps)
                rows.append(
                    {
                        "road_length": road_length,
                        "num_vehicles": num_vehicles,
                        "density": num_vehicles / road_length,
                        "requested_av_share": requested_av_share,
                        "realised_av_share": result["realised_av_share"],
                        "seed": seed,
                        "warmup": warmup,
                        "steps": steps,
                        **result["summary"],
                    }
                )
    return rows


def aggregate_runs(rows: Iterable[dict]) -> list[dict]:
    """Summarise independent runs for every density and requested AV share."""

    groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["density"], row["requested_av_share"])].append(row)

    summaries = []
    for density, requested_av_share in sorted(groups):
        group = groups[(density, requested_av_share)]
        mean_speeds = [row["mean_speed"] for row in group]
        stopped_fractions = [row["stopped_fraction"] for row in group]
        within_run_speed_stds = [row["speed_std"] for row in group]
        summaries.append(
            {
                "density": density,
                "num_vehicles": group[0]["num_vehicles"],
                "requested_av_share": requested_av_share,
                "realised_av_share": fmean(
                    row["realised_av_share"] for row in group
                ),
                "num_runs": len(group),
                "mean_speed_mean": fmean(mean_speeds),
                "mean_speed_seed_sd": _sample_sd(mean_speeds),
                "stopped_fraction_mean": fmean(stopped_fractions),
                "stopped_fraction_seed_sd": _sample_sd(stopped_fractions),
                "within_run_speed_std_mean": fmean(within_run_speed_stds),
                "within_run_speed_std_seed_sd": _sample_sd(within_run_speed_stds),
            }
        )
    return summaries


def _sample_sd(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def write_csv(rows: list[dict], output: Path) -> None:
    if not rows:
        raise ValueError("cannot write an empty result set")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict]) -> None:
    print("| Density | AV share | Runs | Mean speed +/- seed SD | Stopped +/- seed SD |")
    print("|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row['density']:.2f} | {row['realised_av_share']:.0%} | "
            f"{row['num_runs']} | {row['mean_speed_mean']:.3f} +/- "
            f"{row['mean_speed_seed_sd']:.3f} | "
            f"{row['stopped_fraction_mean']:.2%} +/- "
            f"{row['stopped_fraction_seed_sd']:.2%} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=parse_seeds,
        default=list(DEFAULT_SEEDS),
        help="Seed list or ranges (default: 1-20; example: 1-10,21,30-35)",
    )
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args()

    raw_rows = run_experiment(args.seeds)
    summary_rows = aggregate_runs(raw_rows)
    write_csv(raw_rows, args.raw_output)
    write_csv(summary_rows, args.summary_output)
    print_summary(summary_rows)
    print(
        f"\nWrote {len(raw_rows)} runs to {args.raw_output} "
        f"and {len(summary_rows)} summaries to {args.summary_output}"
    )


if __name__ == "__main__":
    main()
