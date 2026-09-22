# Mixed Human and Autonomous Traffic Simulation

CITS4403 group research project investigating how the share of autonomous vehicles affects stop-and-go traffic on a single-lane circular road. The project is completed by two students. The model, experiments, report and demonstration should answer the same research question and be reproducible from the submitted code.

## Research question

How does autonomous vehicle proportion affect traffic stability at different traffic densities in a simplified mixed-traffic model?

The model is designed to investigate this question under explicit simplified rules. It does not claim to predict real-road AV performance.

## Initial scope

- One lane on a circular road; no intersections, entry, exits or lane changes.
- Human and AV vehicles follow explicit, documented update rules.
- Start with a human-only baseline, then add AV behaviour.
- Compare several AV shares at several densities using repeated runs and recorded random seeds.
- Report average speed, stopped-vehicle fraction and speed variation; inspect space-time plots for traffic waves.

See [draft model specification](docs/model-spec.md) for assumptions, proposed measurements and decisions still to make.

## Run the model

Python 3 with the standard library is sufficient. From the repository root:

```powershell
python -m traffic_sim --road-length 200 --vehicles 40 --max-speed 5 --human-slow-prob 0.2 --av-share 0.5 --warmup 200 --steps 800 --seed 7 --csv outputs/mixed-seed7.csv
python -m unittest discover -s tests -v
```

`--av-share` accepts a value from `0` (all human) to `1` (all AV). Human drivers may slow randomly; AVs follow the same acceleration and collision-free gap rules without random slowing. The command prints the configuration and summary metrics as JSON. With `--csv`, it also writes one row per post-warm-up step. `outputs/` is ignored by Git, so reported results should always include their parameters and seeds.

## Reproduce the Checkpoint 2 pilot

The pilot compares 0%, 50% and 100% AV traffic at densities 0.10, 0.20 and 0.30 using seed 7:

```powershell
python -m experiments.checkpoint2_pilot
```

This regenerates `results/checkpoint2-pilot.csv` and prints a compact table. The pilot is an initial demonstration, not the final experiment: the final analysis will use additional AV shares and repeated seeds. See [Checkpoint 2 notes](docs/checkpoint-2.md) for the model explanation, preliminary observations, limitations and next experiment.

## Run the repeated-seed experiment

The final experiment expands the comparison to 0%, 10%, 25%, 50%, 75% and 100% AV traffic at each pilot density. By default it runs seeds 1 through 20 and writes both individual-run results and summaries across seeds:

```powershell
python -m experiments.final_experiment
```

Use `--seeds` to select another reproducible set, including inclusive ranges:

```powershell
python -m experiments.final_experiment --seeds 1-30
```

`results/final-runs.csv` contains one row per independent simulation. `results/final-summary.csv` reports the mean and sample standard deviation across seeds for each density and AV share. The across-seed variation is distinct from `speed_std`, which measures variation among vehicle-speed observations within one simulation.

## Two-person workflow

We use small GitHub issues and pull requests so each member owns a substantive part of the model and reviews the other's work. The morning member starts the human-only baseline and verification. The evening member reviews the baseline, proposes and implements AV behaviour, then suggests the next morning task based on pilot results. Work passes back for experiments, analysis and interpretation. Both members contribute to modelling decisions, the report and the demonstration.

At each handoff, leave a GitHub issue or PR update with what changed, the commands run, any open question, and the next task. Record modelling decisions in docs/model-spec.md so they do not depend on chat history.

The official submission deadline is Friday 9 October 2026 at 11:59 pm. Checkpoint 2 is the next immediate discussion with the facilitator; confirm its exact scheduled time from the unit information.
