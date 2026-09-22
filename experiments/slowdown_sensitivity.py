"""Investigate the effect of varying human slowdown probabilities."""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev
from traffic_sim import SimulationConfig, run_simulation

DEFAULT_OUTPUT = Path("results/slowdown-sensitivity.csv")
ROAD_LENGTH = 200
NUM_VEHICLES = 40
SLOWDOWN_PROBS = (0.0, 0.1, 0.2, 0.3, 0.4)
AV_SHARES = (0.0, 0.50, 1.0)
SEEDS = tuple(range(1, 11))

def run_sensitivity_experiment(output_path: Path) -> list[dict]:
    """Sweeps through 15 conditions across 10 seeds and calculates statistics."""
    raw_data = []
    
    for p_h in SLOWDOWN_PROBS:
        for av_share in AV_SHARES:
            for seed in SEEDS:
                config = SimulationConfig(
                    road_length=ROAD_LENGTH,
                    num_vehicles=NUM_VEHICLES,
                    max_speed=5,
                    human_slow_probability=p_h,
                    av_share=av_share,
                    seed=seed,
                )
                result = run_simulation(config, warmup=200, steps=800)
                
                raw_data.append({
                    "human_slow_probability": p_h,
                    "requested_av_share": av_share,
                    "realised_av_share": result["realised_av_share"],
                    "seed": seed,
                    **result["summary"]
                })

    groups = defaultdict(list)
    for row in raw_data:
        groups[(row["human_slow_probability"], row["requested_av_share"])].append(row)
        
    summary_rows = []
    for (p_h, av_share), runs in sorted(groups.items()):
        speeds = [r["mean_speed"] for r in runs]
        stops = [r["stopped_fraction"] for r in runs]
        stds = [r["speed_std"] for r in runs]
        
        summary_rows.append({
            "human_slow_prob": p_h,
            "av_share": av_share,
            "num_runs": len(runs),
            "mean_speed_mean": fmean(speeds),
            "mean_speed_sd": stdev(speeds) if len(speeds) > 1 else 0.0,
            "stopped_fraction_mean": fmean(stops),
            "stopped_fraction_sd": stdev(stops) if len(stops) > 1 else 0.0,
            "speed_var_mean": fmean(stds),
            "speed_var_sd": stdev(stds) if len(stds) > 1 else 0.0,
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        if summary_rows:
            # FIX: Grabs the keys from the first row element dict inside the list
            writer = csv.DictWriter(stream, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)
        
    return summary_rows

def print_markdown_table(rows: list[dict]) -> None:
    """Prints a clean summary interface straight to the console display."""
    print("\n| p_human | AV Share | Mean Speed +/- SD | Stopped Fraction +/- SD |")
    print("|--------:|---------:|------------------:|------------------------:|")
    for r in rows:
        print(f"| {r['human_slow_prob']:.1f} | {r['av_share']:.0%} | "
              f"{r['mean_speed_mean']:.3f} +/- {r['mean_speed_sd']:.3f} | "
              f"{r['stopped_fraction_mean']:.1%} +/- {r['stopped_fraction_sd']:.1%} |")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    
    print(f"Running 15 sensitivity conditions x 10 seeds...")
    summary_rows = run_sensitivity_experiment(args.output)
    print_markdown_table(summary_rows)
    print(f"\nSaved aggregated matrix summaries to: {args.output}")

if __name__ == "__main__":
    main()
