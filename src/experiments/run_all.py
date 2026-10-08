"""Regenerate every final numerical result, figure and run manifest."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from experiments import final_experiment, robustness, shock_recovery
from experiments.generate_figures import generate_all
from experiments.slowdown_sensitivity import (
    AV_SHARES as SENSITIVITY_AV_SHARES,
    DEFAULT_OUTPUT as SENSITIVITY_OUTPUT,
    SEEDS as SENSITIVITY_SEEDS,
    SLOWDOWN_PROBS,
    run_sensitivity_experiment,
)
from experiments.statistical_analysis import (
    DEFAULT_OUTPUT as STATISTICAL_OUTPUT,
    aggregate_effects,
    calculate_effect_rows,
    write_csv as write_statistical_csv,
)


DEFAULT_METADATA_OUTPUT = Path("results/run-metadata.json")


def run_all(*, quick: bool = False, metadata_output: Path = DEFAULT_METADATA_OUTPUT) -> dict:
    """Run the complete pipeline, with a reduced matrix for smoke testing."""
    final_seeds = (1,) if quick else final_experiment.DEFAULT_SEEDS
    shock_seeds = (1,) if quick else shock_recovery.DEFAULT_SEEDS
    sensitivity_seeds = (1,) if quick else SENSITIVITY_SEEDS
    robustness_seeds = (1,) if quick else robustness.DEFAULT_SEEDS

    final_rows = final_experiment.run_experiment(final_seeds)
    final_summaries = final_experiment.aggregate_runs(final_rows)
    final_experiment.write_csv(final_rows, final_experiment.DEFAULT_RAW_OUTPUT)
    final_experiment.write_csv(
        final_summaries, final_experiment.DEFAULT_SUMMARY_OUTPUT
    )

    run_sensitivity_experiment(
        SENSITIVITY_OUTPUT,
        seeds=sensitivity_seeds,
        slowdown_probs=(0.0, 0.2, 0.4) if quick else SLOWDOWN_PROBS,
        av_shares=SENSITIVITY_AV_SHARES,
    )

    shock_timeseries, shock_rows = shock_recovery.run_shock_experiment(
        shock_seeds,
        lane_counts=shock_recovery.LANE_COUNTS,
    )
    shock_summaries = shock_recovery.aggregate_runs(shock_rows)
    shock_recovery.write_csv(
        shock_timeseries, shock_recovery.DEFAULT_TIMESERIES_OUTPUT
    )
    shock_recovery.write_csv(shock_rows, shock_recovery.DEFAULT_RUNS_OUTPUT)
    shock_recovery.write_csv(
        shock_summaries, shock_recovery.DEFAULT_SUMMARY_OUTPUT
    )

    effect_rows = calculate_effect_rows(shock_rows)
    effect_summaries = aggregate_effects(effect_rows)
    write_statistical_csv(effect_summaries, STATISTICAL_OUTPUT)

    robustness_kwargs = {}
    if quick:
        robustness_kwargs = {
            "scenarios": ((1, 0.5, "anticipatory"),),
            "braking_durations": (8,),
            "recovery_fractions": (0.9, 0.95),
            "warmups": (200,),
        }
    robustness_rows = robustness.run_robustness_experiment(
        robustness_seeds, **robustness_kwargs
    )
    robustness_summaries = robustness.aggregate_robustness(robustness_rows)
    robustness.write_csv(robustness_rows, robustness.DEFAULT_RUNS_OUTPUT)
    robustness.write_csv(
        robustness_summaries, robustness.DEFAULT_SUMMARY_OUTPUT
    )

    figure_outputs = generate_all(
        shock_recovery.DEFAULT_SUMMARY_OUTPUT,
        Path("results/figures"),
        seed=shock_seeds[0],
    )

    outputs = [
        final_experiment.DEFAULT_RAW_OUTPUT,
        final_experiment.DEFAULT_SUMMARY_OUTPUT,
        SENSITIVITY_OUTPUT,
        shock_recovery.DEFAULT_TIMESERIES_OUTPUT,
        shock_recovery.DEFAULT_RUNS_OUTPUT,
        shock_recovery.DEFAULT_SUMMARY_OUTPUT,
        STATISTICAL_OUTPUT,
        robustness.DEFAULT_RUNS_OUTPUT,
        robustness.DEFAULT_SUMMARY_OUTPUT,
        *figure_outputs,
    ]
    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "quick" if quick else "full",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "research_question": (
            "How do autonomous-vehicle penetration and controller strategy affect "
            "the severity and recovery of braking-induced congestion, and how does "
            "safe two-lane passing alter this response?"
        ),
        "seeds": {
            "steady_state": list(final_seeds),
            "shock_recovery": list(shock_seeds),
            "slowdown_sensitivity": list(sensitivity_seeds),
            "robustness": list(robustness_seeds),
        },
        "shock_recovery_design": {
            "road_length": shock_recovery.ROAD_LENGTH,
            "single_lane_vehicle_counts": list(
                shock_recovery.VEHICLE_COUNTS
            ),
            "lane_counts": list(shock_recovery.LANE_COUNTS),
            "av_shares": list(shock_recovery.AV_SHARES),
            "policies": list(shock_recovery.POLICIES),
            "disturbance": {
                "vehicle_id": shock_recovery.DEFAULT_DISTURBANCE.vehicle_id,
                "start_step": shock_recovery.DEFAULT_DISTURBANCE.start_step,
                "duration": shock_recovery.DEFAULT_DISTURBANCE.duration,
                "speed_cap": shock_recovery.DEFAULT_DISTURBANCE.speed_cap,
            },
        },
        "outputs": [path.as_posix() for path in outputs],
        "row_counts": {
            "steady_state_runs": len(final_rows),
            "shock_recovery_runs": len(shock_rows),
            "statistical_summaries": len(effect_summaries),
            "robustness_runs": len(robustness_rows),
        },
    }
    metadata_output.parent.mkdir(parents=True, exist_ok=True)
    metadata_output.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote reproducibility metadata to {metadata_output}")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a reduced matrix for installation and workflow checks",
    )
    parser.add_argument(
        "--metadata-output", type=Path, default=DEFAULT_METADATA_OUTPUT
    )
    args = parser.parse_args()
    run_all(quick=args.quick, metadata_output=args.metadata_output)


if __name__ == "__main__":
    main()
