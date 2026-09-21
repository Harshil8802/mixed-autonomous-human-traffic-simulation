# Checkpoint 2 demonstration notes

## What we are investigating

**Research question:** How does autonomous vehicle proportion affect traffic stability at different traffic densities in a simplified mixed-traffic model?

We use a cellular automaton on a one-lane circular road. Each vehicle occupies one cell, has an integer speed, and reads the same pre-step state before all vehicles move synchronously. This keeps the update order from giving one vehicle an artificial advantage.

## Implemented rules

Each vehicle accelerates by one up to the speed limit, brakes to the available gap so it cannot collide, and then moves. A human driver also has a 0.2 probability of slowing by one cell per step. An AV uses the same acceleration and safe-gap rules but does not slow randomly. This creates a controlled comparison; it is not a claim that real AVs are perfectly deterministic.

The model supports human-only, mixed and AV-only traffic. A seed reproduces initial positions, vehicle types and stochastic decisions. It reports mean speed, stopped-vehicle fraction and speed standard deviation after a warm-up period. Ten automated checks cover state validity, collisions, wraparound gaps, reproducibility, AV allocation and vehicle order.

## Checkpoint 2 pilot

The pilot uses a road of 200 cells, maximum speed 5, human slowing probability 0.2, 200 warm-up steps, 800 measured steps and seed 7. It compares three densities and three AV shares. Run it with:

```powershell
python -m experiments.checkpoint2_pilot
```

The generated results are stored in `results/checkpoint2-pilot.csv`. With this single seed, greater AV share increases mean speed and reduces stopping at every tested density. The benefit is smaller in the densest condition, where the collision-free gap limits every vehicle regardless of type. These are preliminary observations from this model, not final conclusions.

| Density | AV share | Mean speed | Stopped fraction |
|---:|---:|---:|---:|
| 0.10 | 0% | 4.755 | 0.00% |
| 0.10 | 50% | 4.772 | 0.00% |
| 0.10 | 100% | 5.000 | 0.00% |
| 0.20 | 0% | 2.663 | 18.65% |
| 0.20 | 50% | 3.173 | 14.08% |
| 0.20 | 100% | 4.000 | 5.00% |
| 0.30 | 0% | 1.597 | 32.38% |
| 0.30 | 50% | 1.884 | 29.14% |
| 0.30 | 100% | 2.333 | 18.33% |

## Limitations to explain

- The road has one lane, no intersections, no entry or exit, and no lane changing.
- Each vehicle occupies one cell; distance, speed and time are abstract model units.
- AVs have perfect sensing and no random slowing, reaction delay or communication model.
- The pilot uses one seed, so it does not measure run-to-run uncertainty.
- Initial vehicle placement and the human slowing probability are modelling choices rather than calibrated real-road values.

## Next experiment

Run densities 0.10, 0.20 and 0.30 at AV shares 0%, 10%, 25%, 50%, 75% and 100%, with multiple recorded seeds per condition. Summarise the mean and variation across seeds, plot mean speed and stopped fraction against AV share for each density, and create selected space-time diagrams to inspect congestion waves. If a sharp change appears, add AV shares around that region before describing it as a threshold.

## Short speaking order

1. State the research question and why mixed traffic is a complex interacting system.
2. Explain the ring road, synchronous update and human-versus-AV rule.
3. Run one mixed case and show that the test suite passes.
4. Show the nine pilot conditions and describe the preliminary pattern cautiously.
5. Explain the limitations, planned repeated-seed experiment and the questions for the facilitator.

Ask the facilitator whether the focused single-lane model has sufficient depth when combined with the planned systematic experiment and sensitivity analysis, and whether the first AV rule should be compared with a second plausible AV behaviour.
