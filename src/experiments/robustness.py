"""Test whether shock-recovery conclusions depend on analysis choices."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median
from typing import Iterable

from experiments.final_experiment import parse_seeds
from experiments.shock_recovery import (
    _mean_ci95,
    calculate_comparison_window_metrics,
    calculate_recovery_metrics,
    make_pair_id,
)
from traffic_sim import BrakingDisturbance, SimulationConfig, run_simulation


DEFAULT_RUNS_OUTPUT = Path("results/robustness-runs.csv")
DEFAULT_SUMMARY_OUTPUT = Path("results/robustness-summary.csv")
DEFAULT_SEEDS = tuple(range(1, 6))
SCENARIOS = (
    (1, 0.0, "reactive"),
    (1, 0.5, "anticipatory"),
    (2, 0.5, "anticipatory"),
)
BRAKING_DURATIONS = (4, 8, 12)
RECOVERY_FRACTIONS = (0.90, 0.95)
WARMUPS = (200, 400)


def run_robustness_experiment(
    seeds: Iterable[int],
    *,
    scenarios: Iterable[tuple[int, float, str]] = SCENARIOS,
    braking_durations: Iterable[int] = BRAKING_DURATIONS,
    recovery_fractions: Iterable[float] = RECOVERY_FRACTIONS,
    warmups: Iterable[int] = WARMUPS,
    road_length: int = 200,
    single_lane_vehicle_count: int = 60,
    steps: int = 400,
    disturbance_start: int = 100,
    recovery_window: int = 20,
) -> list[dict]:
    """Run a compact sensitivity matrix with paired no-shock controls."""
    seed_values = tuple(seeds)
    if not seed_values:
        raise ValueError("at least one seed is required")
    rows = []
    density = single_lane_vehicle_count / road_length
    for lanes, av_share, policy in scenarios:
        for warmup in warmups:
            for duration in braking_durations:
                disturbance = BrakingDisturbance(
                    vehicle_id=0,
                    start_step=disturbance_start,
                    duration=duration,
                    speed_cap=0,
                )
                for seed in seed_values:
                    config = SimulationConfig(
                        road_length=road_length,
                        num_vehicles=single_lane_vehicle_count * lanes,
                        max_speed=5,
                        human_slow_probability=0.2,
                        av_share=av_share,
                        av_policy=policy,
                        lanes=lanes,
                        seed=seed,
                    )
                    shocked = run_simulation(
                        config,
                        warmup=warmup,
                        steps=steps,
                        disturbance=disturbance,
                    )
                    control = run_simulation(config, warmup=warmup, steps=steps)
                    control_window = calculate_comparison_window_metrics(
                        control["per_step"], disturbance
                    )
                    for recovery_fraction in recovery_fractions:
                        recovery = calculate_recovery_metrics(
                            shocked["per_step"],
                            disturbance,
                            recovery_window=recovery_window,
                            recovery_fraction=recovery_fraction,
                        )
                        rows.append(
                            {
                                "pair_id": make_pair_id(
                                    lanes=lanes,
                                    density=density,
                                    requested_av_share=av_share,
                                    av_policy=policy,
                                    seed=seed,
                                ),
                                "lanes": lanes,
                                "density": density,
                                "requested_av_share": av_share,
                                "av_policy": policy,
                                "seed": seed,
                                "warmup": warmup,
                                "steps": steps,
                                "braking_duration": duration,
                                "disturbance_start_step": disturbance_start,
                                "disturbance_speed_cap": 0,
                                "recovery_window": recovery_window,
                                "recovery_fraction": recovery_fraction,
                                **recovery,
                                "maximum_stopped_fraction_delta_from_control": recovery[
                                    "maximum_stopped_fraction_after_braking"
                                ]
                                - control_window["maximum_stopped_fraction"],
                                "minimum_mean_speed_delta_from_control": recovery[
                                    "minimum_mean_speed_after_braking"
                                ]
                                - control_window["minimum_mean_speed"],
                            }
                        )
    return rows


def aggregate_robustness(rows: Iterable[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    fields = (
        "lanes",
        "density",
        "requested_av_share",
        "av_policy",
        "warmup",
        "braking_duration",
        "recovery_window",
        "recovery_fraction",
    )
    for row in rows:
        groups[tuple(row[field] for field in fields)].append(row)

    summaries = []
    for key in sorted(groups):
        group = groups[key]
        recovery_times = [
            row["recovery_time_steps"]
            for row in group
            if row["recovery_time_steps"] is not None
        ]
        stopped_deltas = [
            row["maximum_stopped_fraction_delta_from_control"] for row in group
        ]
        recovery_ci = _mean_ci95(recovery_times)
        stopped_ci = _mean_ci95(stopped_deltas)
        summary = dict(zip(fields, key))
        summary.update(
            {
                "num_runs": len(group),
                "recovered_runs": len(recovery_times),
                "recovery_rate": len(recovery_times) / len(group),
                "recovery_time_mean": (
                    fmean(recovery_times) if recovery_times else None
                ),
                "recovery_time_median": (
                    median(recovery_times) if recovery_times else None
                ),
                "recovery_time_ci95_low": recovery_ci[0],
                "recovery_time_ci95_high": recovery_ci[1],
                "maximum_stopped_delta_mean": fmean(stopped_deltas),
                "maximum_stopped_delta_ci95_low": stopped_ci[0],
                "maximum_stopped_delta_ci95_high": stopped_ci[1],
            }
        )
        summaries.append(summary)
    return summaries


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        raise ValueError("cannot write an empty robustness result set")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        type=parse_seeds,
        default=list(DEFAULT_SEEDS),
        help="Seed list or ranges (default: 1-5)",
    )
    parser.add_argument("--runs-output", type=Path, default=DEFAULT_RUNS_OUTPUT)
    parser.add_argument(
        "--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT
    )
    args = parser.parse_args()

    rows = run_robustness_experiment(args.seeds)
    summaries = aggregate_robustness(rows)
    write_csv(rows, args.runs_output)
    write_csv(summaries, args.summary_output)
    print(
        f"Wrote {len(rows)} robustness runs to {args.runs_output} and "
        f"{len(summaries)} summaries to {args.summary_output}"
    )


if __name__ == "__main__":
    main()
