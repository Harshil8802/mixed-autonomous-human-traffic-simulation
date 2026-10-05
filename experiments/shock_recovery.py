"""Measure traffic disruption and recovery after a controlled braking event."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, median, quantiles, stdev
from typing import Iterable

from experiments.final_experiment import parse_seeds
from traffic_sim import BrakingDisturbance, SimulationConfig, run_simulation


DEFAULT_TIMESERIES_OUTPUT = Path("results/shock-recovery-timeseries.csv")
DEFAULT_RUNS_OUTPUT = Path("results/shock-recovery-runs.csv")
DEFAULT_SUMMARY_OUTPUT = Path("results/shock-recovery-summary.csv")
ROAD_LENGTH = 200
# Vehicle counts describe the equivalent single-lane occupancy. Two-lane runs
# multiply these counts by two to preserve N / (road_length * lanes).
VEHICLE_COUNTS = (40, 60)
LANE_COUNTS = (1, 2)
AV_SHARES = (0.0, 0.25, 0.50, 0.75, 1.0)
POLICIES = ("reactive", "anticipatory")
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
    lane_counts: Iterable[int] = (1,),
    av_shares: Iterable[float] = AV_SHARES,
    policies: Iterable[str] = POLICIES,
    human_slow_probability: float = 0.2,
    warmup: int = 200,
    steps: int = 400,
    disturbance: BrakingDisturbance = DEFAULT_DISTURBANCE,
    recovery_window: int = 20,
    timeseries_seeds: Iterable[int] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Run shock-recovery conditions at equal occupancy across lane counts.

    ``vehicle_counts`` contains the number of vehicles for the equivalent
    single-lane condition. For ``K`` lanes, the simulation uses ``K`` times
    that count so density remains ``N / (road_length * K)``.
    """
    seed_values = tuple(seeds)
    if not seed_values:
        raise ValueError("at least one seed is required")
    lane_values = tuple(dict.fromkeys(lane_counts))
    if not lane_values:
        raise ValueError("at least one lane count is required")
    if any(lanes not in (1, 2) for lanes in lane_values):
        raise ValueError("lane counts must be 1 or 2")
    single_lane_vehicle_counts = tuple(vehicle_counts)
    if not single_lane_vehicle_counts:
        raise ValueError("at least one vehicle count is required")
    share_values = tuple(av_shares)
    if not share_values:
        raise ValueError("at least one AV share is required")
    policy_values = tuple(dict.fromkeys(policies))
    if not policy_values:
        raise ValueError("at least one AV policy is required")
    if any(policy not in POLICIES for policy in policy_values):
        raise ValueError("AV policies must be reactive or anticipatory")
    selected_timeseries_seeds = set(
        timeseries_seeds if timeseries_seeds is not None else (seed_values[0],)
    )

    timeseries_rows: list[dict] = []
    run_rows: list[dict] = []
    for lanes in lane_values:
        for single_lane_vehicle_count in single_lane_vehicle_counts:
            num_vehicles = single_lane_vehicle_count * lanes
            road_cells = road_length * lanes
            density = num_vehicles / road_cells
            for requested_av_share in share_values:
                active_policies = (
                    ("reactive",)
                    if requested_av_share == 0.0
                    else policy_values
                )
                for policy in active_policies:
                    for seed in seed_values:
                        config = SimulationConfig(
                            road_length=road_length,
                            num_vehicles=num_vehicles,
                            max_speed=5,
                            human_slow_probability=human_slow_probability,
                            av_share=requested_av_share,
                            seed=seed,
                            av_policy=policy,
                            lanes=lanes,
                        )
                        result = run_simulation(
                            config,
                            warmup=warmup,
                            steps=steps,
                            disturbance=disturbance,
                        )
                        control_result = run_simulation(
                            config,
                            warmup=warmup,
                            steps=steps,
                        )
                        recovery = calculate_recovery_metrics(
                            result["per_step"],
                            disturbance,
                            recovery_window=recovery_window,
                        )
                        control_window = calculate_comparison_window_metrics(
                            control_result["per_step"], disturbance
                        )
                        disturbed_vehicle = next(
                            vehicle
                            for vehicle in result["measurement_start_state"]
                            if vehicle["vehicle_id"] == disturbance.vehicle_id
                        )
                        pair_id = make_pair_id(
                            lanes=lanes,
                            density=density,
                            requested_av_share=requested_av_share,
                            av_policy=policy,
                            seed=seed,
                        )
                        run_rows.append(
                            {
                                "pair_id": pair_id,
                                "road_length": road_length,
                                "lanes": lanes,
                                "road_cells": road_cells,
                                "num_vehicles": num_vehicles,
                                "density": density,
                                "requested_av_share": requested_av_share,
                                "realised_av_share": result["realised_av_share"],
                                "av_policy": policy,
                                "seed": seed,
                                "warmup": warmup,
                                "steps": steps,
                                "disturbance_vehicle_id": disturbance.vehicle_id,
                                "disturbance_start_step": disturbance.start_step,
                                "disturbance_duration": disturbance.duration,
                                "disturbance_speed_cap": disturbance.speed_cap,
                                "disturbed_vehicle_type": disturbed_vehicle[
                                    "vehicle_type"
                                ],
                                "disturbed_vehicle_initial_lane": disturbed_vehicle[
                                    "lane"
                                ],
                                "mean_speed": result["summary"]["mean_speed"],
                                "stopped_fraction": result["summary"]["stopped_fraction"],
                                "speed_std": result["summary"]["speed_std"],
                                "traffic_flow": density
                                * result["summary"]["mean_speed"],
                                "control_mean_speed": control_result["summary"][
                                    "mean_speed"
                                ],
                                "control_stopped_fraction": control_result["summary"][
                                    "stopped_fraction"
                                ],
                                "control_speed_std": control_result["summary"][
                                    "speed_std"
                                ],
                                "mean_speed_delta_from_control": result["summary"][
                                    "mean_speed"
                                ]
                                - control_result["summary"]["mean_speed"],
                                "stopped_fraction_delta_from_control": result[
                                    "summary"
                                ]["stopped_fraction"]
                                - control_result["summary"]["stopped_fraction"],
                                "minimum_mean_speed_delta_from_control": recovery[
                                    "minimum_mean_speed_after_braking"
                                ]
                                - control_window["minimum_mean_speed"],
                                "maximum_stopped_fraction_delta_from_control": recovery[
                                    "maximum_stopped_fraction_after_braking"
                                ]
                                - control_window["maximum_stopped_fraction"],
                                **recovery,
                            }
                        )

                        if seed in selected_timeseries_seeds:
                            for row in result["per_step"]:
                                timeseries_rows.append(
                                    {
                                        "road_length": road_length,
                                        "lanes": lanes,
                                        "road_cells": road_cells,
                                        "num_vehicles": num_vehicles,
                                        "density": density,
                                        "requested_av_share": requested_av_share,
                                        "realised_av_share": result[
                                            "realised_av_share"
                                        ],
                                        "av_policy": policy,
                                        "seed": seed,
                                        **row,
                                        "traffic_flow": density
                                        * row["mean_speed"],
                                    }
                                )
    return timeseries_rows, run_rows


def calculate_comparison_window_metrics(
    per_step: list[dict], disturbance: BrakingDisturbance
) -> dict[str, float]:
    """Measure a control run over the same window used for shock severity."""
    comparison_rows = [
        row for row in per_step if row["step"] >= disturbance.start_step
    ]
    if not comparison_rows:
        raise ValueError("comparison window must begin within the measurements")
    return {
        "minimum_mean_speed": min(row["mean_speed"] for row in comparison_rows),
        "maximum_stopped_fraction": max(
            row["stopped_fraction"] for row in comparison_rows
        ),
    }


def make_pair_id(
    *,
    lanes: int,
    density: float,
    requested_av_share: float,
    av_policy: str,
    seed: int,
) -> str:
    """Return a stable identifier for a disturbed/control run pair."""
    return (
        f"lanes-{lanes}_density-{density:.3f}_av-{requested_av_share:.3f}_"
        f"policy-{av_policy}_seed-{seed}"
    )


def aggregate_runs(rows: Iterable[dict]) -> list[dict]:
    """Summarise independent shock-recovery runs across seeds and policies."""
    groups: dict[tuple[int, float, float, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (
            row["lanes"],
            row["density"],
            row["requested_av_share"],
            row["av_policy"],
        )
        groups[key].append(row)

    summaries = []
    for lanes, density, requested_av_share, av_policy in sorted(groups):
        group = groups[(lanes, density, requested_av_share, av_policy)]
        recovered_times = [
            row["recovery_time_steps"]
            for row in group
            if row["recovery_time_steps"] is not None
        ]
        maximum_stopped_values = [
            row["maximum_stopped_fraction_after_braking"] for row in group
        ]
        recovery_ci = _mean_ci95(recovered_times)
        stopped_ci = _mean_ci95(maximum_stopped_values)
        recovery_quartiles = _quartiles(recovered_times)
        summaries.append(
            {
                "road_length": group[0]["road_length"],
                "lanes": lanes,
                "road_cells": group[0]["road_cells"],
                "density": density,
                "num_vehicles": group[0]["num_vehicles"],
                "requested_av_share": requested_av_share,
                "realised_av_share": fmean(row["realised_av_share"] for row in group),
                "av_policy": av_policy,
                "num_runs": len(group),
                "recovered_runs": len(recovered_times),
                "recovery_rate": len(recovered_times) / len(group),
                "mean_speed_mean": fmean(row["mean_speed"] for row in group),
                "mean_speed_seed_sd": _sample_sd([row["mean_speed"] for row in group]),
                "stopped_fraction_mean": fmean(row["stopped_fraction"] for row in group),
                "stopped_fraction_seed_sd": _sample_sd([row["stopped_fraction"] for row in group]),
                "within_run_speed_std_mean": fmean(row["speed_std"] for row in group),
                "traffic_flow_mean": fmean(row["traffic_flow"] for row in group),
                "mean_speed_delta_from_control_mean": fmean(
                    row["mean_speed_delta_from_control"] for row in group
                ),
                "stopped_fraction_delta_from_control_mean": fmean(
                    row["stopped_fraction_delta_from_control"] for row in group
                ),
                "minimum_mean_speed_delta_from_control_mean": fmean(
                    row["minimum_mean_speed_delta_from_control"] for row in group
                ),
                "maximum_stopped_fraction_delta_from_control_mean": fmean(
                    row["maximum_stopped_fraction_delta_from_control"]
                    for row in group
                ),
                "pre_disturbance_mean_speed_mean": fmean(row["pre_disturbance_mean_speed"] for row in group),
                "minimum_mean_speed_after_braking_mean": fmean(row["minimum_mean_speed_after_braking"] for row in group),
                "maximum_stopped_fraction_after_braking_mean": fmean(row["maximum_stopped_fraction_after_braking"] for row in group),
                "maximum_stopped_fraction_after_braking_ci95_low": stopped_ci[0],
                "maximum_stopped_fraction_after_braking_ci95_high": stopped_ci[1],
                "recovery_time_steps_mean": fmean(recovered_times) if recovered_times else None,
                "recovery_time_steps_seed_sd": _sample_sd(recovered_times) if recovered_times else None,
                "recovery_time_steps_ci95_low": recovery_ci[0],
                "recovery_time_steps_ci95_high": recovery_ci[1],
                "recovery_time_steps_median": (
                    median(recovered_times) if recovered_times else None
                ),
                "recovery_time_steps_q1": recovery_quartiles[0],
                "recovery_time_steps_q3": recovery_quartiles[1],
            }
        )
    return summaries


def _sample_sd(values: list[float]) -> float:
    return stdev(values) if len(values) > 1 else 0.0


def _mean_ci95(values: list[float]) -> tuple[float | None, float | None]:
    """Return a two-sided 95% t interval for independent run values."""
    if not values:
        return None, None
    mean = fmean(values)
    if len(values) == 1:
        return mean, mean
    t_critical = {
        1: 12.706,
        2: 4.303,
        3: 3.182,
        4: 2.776,
        5: 2.571,
        6: 2.447,
        7: 2.365,
        8: 2.306,
        9: 2.262,
        10: 2.228,
        11: 2.201,
        12: 2.179,
        13: 2.160,
        14: 2.145,
        15: 2.131,
        16: 2.120,
        17: 2.110,
        18: 2.101,
        19: 2.093,
        20: 2.086,
        25: 2.060,
        30: 2.042,
    }
    degrees_freedom = len(values) - 1
    critical = next(
        (
            value
            for df, value in sorted(t_critical.items())
            if degrees_freedom <= df
        ),
        1.96,
    )
    margin = critical * stdev(values) / math.sqrt(len(values))
    return mean - margin, mean + margin


def _quartiles(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], values[0]
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    return q1, q3


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
        "\n| Lanes | Density | AV share | Policy | Runs | Recov | "
        "Max Stop Break | Recov Time +/- SD |"
    )
    print("|---:|---:|---:|:---|---:|---:|---:|---:|")
    for r in rows:
        rec_time = (
            f"{r['recovery_time_steps_mean']:.1f} +/- "
            f"{r['recovery_time_steps_seed_sd']:.1f}"
            if r["recovery_time_steps_mean"] is not None
            else "N/A"
        )
        print(
            f"| {r['lanes']} | {r['density']:.2f} | "
            f"{r['realised_av_share']:.0%} | "
            f"{r['av_policy']:<12} | {r['num_runs']} | {r['recovered_runs']} | "
            f"{r['maximum_stopped_fraction_after_braking_mean']:.1%} | "
            f"{rec_time} |"
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
        "--policy",
        choices=list(POLICIES) + ["all"],
        default="all",
        help="AV policy to evaluate (default: all)",
    )
    parser.add_argument(
        "--lanes",
        choices=("1", "2", "all"),
        default="all",
        help="Lane counts to evaluate (default: all)",
    )
    parser.add_argument("--timeseries-output", type=Path, default=DEFAULT_TIMESERIES_OUTPUT)
    parser.add_argument("--runs-output", type=Path, default=DEFAULT_RUNS_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    args = parser.parse_args()

    selected_policies = POLICIES if args.policy == "all" else (args.policy,)
    selected_lanes = LANE_COUNTS if args.lanes == "all" else (int(args.lanes),)
    timeseries_rows, run_rows = run_shock_experiment(
        args.seeds,
        policies=selected_policies,
        lane_counts=selected_lanes,
    )
    summary_rows = aggregate_runs(run_rows)
    
    write_csv(timeseries_rows, args.timeseries_output)
    write_csv(run_rows, args.runs_output)
    write_csv(summary_rows, args.summary_output)
    print_summary(summary_rows)


if __name__ == "__main__":
    main()
