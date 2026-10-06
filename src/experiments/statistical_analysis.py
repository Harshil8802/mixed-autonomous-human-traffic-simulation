"""Calculate paired treatment effects from shock-recovery run results."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Iterable

from experiments.shock_recovery import _mean_ci95


DEFAULT_INPUT = Path("results/shock-recovery-runs.csv")
DEFAULT_OUTPUT = Path("results/statistical-effects.csv")
IDENTITY_FIELDS = (
    "lanes",
    "density",
    "requested_av_share",
    "av_policy",
    "seed",
)
OUTCOME_FIELDS = (
    "maximum_stopped_fraction_after_braking",
    "recovery_time_steps",
)


def _optional_float(value: object) -> float | None:
    if value in (None, "", "None", "N/A"):
        return None
    return float(value)


def read_run_rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("shock-recovery run file is empty")
    numeric_fields = {
        "lanes",
        "density",
        "requested_av_share",
        "seed",
        *OUTCOME_FIELDS,
        "maximum_stopped_fraction_delta_from_control",
    }
    return [
        {
            key: _optional_float(value) if key in numeric_fields else value
            for key, value in row.items()
        }
        for row in rows
    ]


def calculate_effect_rows(rows: Iterable[dict]) -> list[dict]:
    """Calculate within-seed effects relative to scientific reference cases."""
    values = list(rows)
    zero_av = {
        (int(row["lanes"]), row["density"], int(row["seed"])): row
        for row in values
        if row["requested_av_share"] == 0.0 and row["av_policy"] == "reactive"
    }
    reactive = {
        (
            int(row["lanes"]),
            row["density"],
            row["requested_av_share"],
            int(row["seed"]),
        ): row
        for row in values
        if row["av_policy"] == "reactive"
    }
    one_lane = {
        (
            row["density"],
            row["requested_av_share"],
            row["av_policy"],
            int(row["seed"]),
        ): row
        for row in values
        if int(row["lanes"]) == 1
    }

    effect_rows = []
    for row in values:
        lanes = int(row["lanes"])
        seed = int(row["seed"])
        references = {
            "zero_av": zero_av.get((lanes, row["density"], seed)),
            "reactive": reactive.get(
                (lanes, row["density"], row["requested_av_share"], seed)
            ),
            "one_lane": one_lane.get(
                (
                    row["density"],
                    row["requested_av_share"],
                    row["av_policy"],
                    seed,
                )
            ),
        }
        effect = {field: row[field] for field in IDENTITY_FIELDS}
        effect["pair_id"] = row.get("pair_id", "")
        effect["maximum_stopped_effect_vs_matched_control"] = row.get(
            "maximum_stopped_fraction_delta_from_control"
        )
        for reference_name, reference in references.items():
            for outcome in OUTCOME_FIELDS:
                current_value = row.get(outcome)
                reference_value = reference.get(outcome) if reference else None
                effect[f"{outcome}_effect_vs_{reference_name}"] = (
                    current_value - reference_value
                    if current_value is not None and reference_value is not None
                    else None
                )
        effect_rows.append(effect)
    return effect_rows


def aggregate_effects(rows: Iterable[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in IDENTITY_FIELDS[:-1])
        groups[key].append(row)

    metric_names = sorted(
        {
            name
            for group in groups.values()
            for name in group[0]
            if "_effect_" in name
        }
    )
    summaries = []
    for key in sorted(groups):
        group = groups[key]
        summary = dict(zip(IDENTITY_FIELDS[:-1], key))
        summary["num_runs"] = len(group)
        for metric in metric_names:
            metric_values = [
                value
                for row in group
                if (value := row.get(metric)) is not None
            ]
            low, high = _mean_ci95(metric_values)
            summary[f"{metric}_n"] = len(metric_values)
            summary[f"{metric}_mean"] = (
                fmean(metric_values) if metric_values else None
            )
            summary[f"{metric}_ci95_low"] = low
            summary[f"{metric}_ci95_high"] = high
        summaries.append(summary)
    return summaries


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        raise ValueError("cannot write an empty statistical result set")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    run_rows = read_run_rows(args.input)
    effect_rows = calculate_effect_rows(run_rows)
    summaries = aggregate_effects(effect_rows)
    write_csv(summaries, args.output)
    print(f"Wrote {len(summaries)} statistical summaries to {args.output}")


if __name__ == "__main__":
    main()
