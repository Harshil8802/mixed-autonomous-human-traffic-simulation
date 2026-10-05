"""Benchmark a representative dense two-lane simulation."""

from __future__ import annotations

import argparse
import json
from statistics import fmean
from time import perf_counter

from traffic_sim import SimulationConfig, run_simulation


def benchmark(*, repeats: int = 3, warmup: int = 200, steps: int = 400) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    config = SimulationConfig(
        road_length=200,
        num_vehicles=120,
        lanes=2,
        av_share=0.5,
        av_policy="anticipatory",
        human_slow_probability=0.2,
        seed=7,
    )
    elapsed = []
    for _ in range(repeats):
        started = perf_counter()
        run_simulation(config, warmup=warmup, steps=steps)
        elapsed.append(perf_counter() - started)
    return {
        "repeats": repeats,
        "warmup": warmup,
        "steps": steps,
        "elapsed_seconds": elapsed,
        "mean_seconds": fmean(elapsed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=200)
    parser.add_argument("--steps", type=int, default=400)
    args = parser.parse_args()
    print(
        json.dumps(
            benchmark(
                repeats=args.repeats,
                warmup=args.warmup,
                steps=args.steps,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
