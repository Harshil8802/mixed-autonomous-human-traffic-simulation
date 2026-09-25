"""Measure traffic disruption and recovery after a controlled braking event."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev
from typing import Iterable

from experiments.final_experiment import parse_seeds
from traffic_sim import BrakingDisturbance, SimulationConfig, run_simulation


DEFAULT_TIMESERIES_OUTPUT = Path("results/shock-recovery-timeseries.csv")
DEFAULT_RUNS_OUTPUT = Path("results/shock-recovery-runs.csv")
DEFAULT_SUMMARY_OUTPUT = Path("results/shock-recovery-summary.csv")
ROAD_LENGTH = 200
VEHICLE_COUNTS = (40, 60)
AV_SHARES = (0.0, 0.25, 0.50, 0.75, 1.0)
DEFAULT_SEEDS = tuple(range(1, 11))
DEFAULT_DISTURBANCE = BrakingDisturbance(
    vehicle_id=0,
    start_step=100,
    duration=8,
    speed_cap=0,
)


def calculate_recovery_metrics(
    per_step: list[dict],
    disturbance: BrakingDisturbance,
    *,
    recovery_window: int = 20,
    recovery_fraction: float = 0.95,
) -> dict:
    """Calculate disruption severity and recovery from per-step measurements."""

    if recovery_window < 1:
        raise ValueError("recovery_window must be positive")
    if not 0 < recovery_fraction <= 1:
        raise ValueError("recovery_fraction must be between 0 and 1")

    baseline_rows = [row for row in per_step if row["step"] < disturbance.start_step]
    affected_rows = [row for row in per_step if row["step"] >= disturbance.start_step]
    post_rows = [row for row in per_step if row["step"] > disturbance.end_step]
    if not baseline_rows:
        raise ValueError("at least one pre-disturbance measurement is required")
    if not affected_rows:
        raise ValueError("the disturbance must begin within the measurements")

    baseline_speed = fmean(row["mean_speed"] for row in baseline_rows)
    threshold = baseline_speed * recovery_fraction
    recovery_time = None
    for index in range(recovery_window - 1, len(post_rows)):
        window = post_rows[index - recovery_window + 1 : index + 1]
        if fmean(row["mean_speed"] for row in window) >= threshold:
            recovery_time = post_rows[index]["step"] - disturbance.end_step
            break

    return {
        "pre_disturbance_mean_speed": baseline_speed,
        "minimum_mean_speed_after_braking": min(
            row["mean_speed"] for row in affected_rows
        ),
        "maximum_stopped_fraction_after_braking": max(
            row["stopped_fraction"] for row in affected_rows
        ),
        "recovered": recovery_time is not None,
        "recovery_time_steps": recovery_time,
    }


def run_shock_experiment(
    seeds: Iterable[int],
    *,
    road_length: int = ROAD_LENGTH,
    vehicle_counts: Iterable[int] = VEHICLE_COUNTS,
    av_shares: Iterable[float] = AV_SHARES,
    human_slow_probability: float = 0.2,
    warmup: int = 200,
    steps: int = 400,
    disturbance: BrakingDisturbance = DEFAULT_DISTURBANCE,
    recovery_window: int = 20,
    timeseries_seeds: Iterable[int] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Run shock-recovery conditions and retain selected per-step time series."""

    seed_values = tuple(seeds)
    if not seed_values:
        raise ValueError("at least one seed is required")
    selected_timeseries_seeds = set(
        timeseries_seeds if timeseries_seeds is not None else (seed_values[0],)
    )

    timeseries_rows: list[dict] = []
    run_rows: list[dict] = []
    for num_vehicles in vehicle_counts:
        density = num_vehicles / road_length
        for requested_av_share in av_shares:
            for seed in seed_values:
                config = SimulationConfig(
                    road_length=road_length,
                    num_vehicles=num_vehicles,
                    max_speed=5,
                    human_slow_probability=human_slow_probability,
                    av_share=requested_av_share,
                    seed=seed,
                )
                result = run_simulation(
                    config,
                    warmup=warmup,
                    steps=steps,
                    disturbance=disturbance,
                )
                recovery = calculate_recovery_metrics(
                    result["per_step"],
                    disturbance,
                    recovery_window=recovery_window,
                )
                run_rows.append(
                    {
                        "road_length": road_length,
                        "num_vehicles": num_vehicles,
                        "density": density,
                        "requested_av_share": requested_av_share,
                        "realised_av_share": result["realised_av_share"],
                        "seed": seed,
                        "warmup": warmup,
                        "steps": steps,
                        "disturbance_vehicle_id": disturbance.vehicle_id,
                        "disturbance_start_step": disturbance.start_step,
                        "disturbance_duration": disturbance.duration,
                        "disturbance_speed_cap": disturbance.speed_cap,
                        "mean_speed": result["summary"]["mean_speed"],
                        "stopped_fraction": result["summary"]["stopped_fraction"],
                        "speed_std": result["summary"]["speed_std"],
                        "traffic_flow": density * result["summary"]["mean_speed"],
                        **recovery,
                    }
                )

                if seed in selected_timeseries_seeds:
                    for row in result["per_step"]:
                        timeseries_rows.append(
                            {
                                "road_length": road_length,
                                "num_vehicles": num_vehicles,
                                "density": density,
                                "requested_av_share": requested_av_share,
                                "realised_av_share": result["realised_av_share"],
                                "seed": seed,
                                **row,
                                "traffic_flow": density * row["mean_speed"],
                            }
                        )
    return timeseries_rows, run_rows


def aggregate_runs(rows: Iterable[dict]) -> list[dict]:
    """Summarise independent shock-recovery runs across seeds."""

    groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["density"], row["requested_av_share"])].append(row)

    summaries = []
    for density, requested_av_share in sorted(groups):
        group = groups[(density, requested_av_share)]
        recovered_times = [
            row["recovery_time_steps"]
            for row in group
            if row["recovery_time_steps"] is not None
        ]
        summaries.append(
            {
                "density": density,
                "num_vehicles": group[0]["num_vehicles"],
                "requested_av_share": requested_av_share,
                "realised_av_share": fmean(
                    row["realised_av_share"] for row in group
                ),
                "num_runs": len(group),
                "recovered_runs": len(recovered_times),
                "mean_speed_mean": fmean(row["mean_speed"] for row in group),
                "mean_speed_seed_sd": _sample_sd(
                    [row["mean_speed"] for row in group]
                ),
                "stopped_fraction_mean": fmean(
                    row["stopped_fraction"] for row in group
                ),
                "stopped_fraction_seed_sd": _sample_sd(
                    [row["stopped_fraction"] for row in group]
                ),
                "within_run_speed_std_mean": fmean(
                    row["speed_std"] for row in group
                ),
                "traffic_flow_mean": fmean(row["traffic_flow"] for row in group),
                "pre_disturbance_mean_speed_mean": fmean(
                    row["pre_disturbance_mean_speed"] for row in group
                ),
                "minimum_mean_speed_after_braking_mean": fmean(
                    row["minimum_mean_speed_after_braking"] for row in group
                ),
                "maximum_stopped_fraction_after_braking_mean": fmean(
                    row["maximum_stopped_fraction_after_braking"] for row in group
                ),
                "recovery_time_mean": (
                    fmean(recovered_times) if recovered_times else None
                ),
                "recovery_time_seed_sd": _sample_sd(recovered_times),
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
    print(
        "| Density | AV share | Runs | Mean speed | Min after brake | "
        "Max stopped | Recovery steps |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        recovery = (
            f"{row['recovery_time_mean']:.1f}"
            if row["recovery_time_mean"] is not None
            else "not observed"
        )
        print(
            f"| {row['density']:.2f} | {row['realised_av_share']:.0%} | "
            f"{row['num_runs']} | {row['mean_speed_mean']:.3f} | "
            f"{row['minimum_mean_speed_after_braking_mean']:.3f} | "
            f"{row['maximum_stopped_fraction_after_braking_mean']:.1%} | "
            f"{recovery} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=parse_seeds,
        default=list(DEFAULT_SEEDS),
        help="Seed list or ranges (default: 1-10)",
    )
    parser.add_argument(
        "--timeseries-output", type=Path, default=DEFAULT_TIMESERIES_OUTPUT
    )
    parser.add_argument("--runs-output", type=Path, default=DEFAULT_RUNS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args()

    timeseries_rows, run_rows = run_shock_experiment(args.seeds)
    summary_rows = aggregate_runs(run_rows)
    write_csv(timeseries_rows, args.timeseries_output)
    write_csv(run_rows, args.runs_output)
    write_csv(summary_rows, args.summary_output)
    print_summary(summary_rows)
    print(
        f"\nWrote {len(timeseries_rows)} representative time-series rows to "
        f"{args.timeseries_output}, {len(run_rows)} runs to {args.runs_output}, "
        f"and {len(summary_rows)} summaries to {args.summary_output}."
    )


if __name__ == "__main__":
    main()
