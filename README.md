# Mixed Human and Autonomous Traffic Resilience Simulation

This CITS4403 group research project investigates how mixed human and autonomous traffic responds to a controlled braking disturbance. A discrete circular-road model supplies a transparent baseline; the research contribution is the systematic comparison of autonomous-vehicle penetration, controller strategy and lane-changing access using reproducible shock-recovery experiments. The model is an exploratory complex-systems model, not a calibrated predictor of real-road AV performance.

## Research question

**How do autonomous-vehicle penetration and controller strategy affect the severity and recovery of braking-induced congestion, and how does safe two-lane passing alter this response?**

## Originality and contribution

Traffic jams on a simple ring road are a taught example in CITS4403, so reproducing that baseline is not presented as the project's original contribution. The baseline is used as a controlled reference against which the team investigates five extensions:

- mixed human and autonomous traffic at several AV penetration levels;
- reactive and anticipatory AV controller assumptions;
- a repeatable braking intervention and explicit recovery measurements;
- safe symmetric passing on a parallel two-lane ring; and
- sensitivity to the probability of unpredictable human slowing.

The added value is a controlled analysis of traffic resilience: whether a disturbance grows or dissipates, how long recovery takes, and whether the conclusion changes with controller design or access to an adjacent lane. Comparisons use repeated random seeds and report variation across runs.

## Implemented scope

- One- and two-lane circular roads with no intersections, entry or exit.
- Human, reactive-AV and anticipatory-AV update rules.
- Reproducible initialisation with recorded seeds and synchronous movement.
- Steady-state, sensitivity and controlled shock-recovery experiments.
- Quantitative measures including mean speed, stopped fraction, speed variation, disruption severity and recovery time.

See the [model specification](docs/model-spec.md) for assumptions, update rules, experimental controls and limitations.

## Run the model

Python 3 with the standard library is sufficient. From the repository root:

```powershell
python -m traffic_sim --road-length 200 --vehicles 80 --lanes 2 --max-speed 5 --human-slow-prob 0.2 --av-share 0.5 --av-policy anticipatory --warmup 200 --steps 800 --seed 7 --csv outputs/mixed-seed7.csv
python -m unittest discover -s tests -v
```

For a repeatable local performance check of the dense two-lane model, run:

```powershell
python -m experiments.benchmark_model
```

`--lanes` selects a one- or two-lane circular road, `--av-policy` selects the reactive or anticipatory AV controller, and `--av-share` accepts a value from `0` (all human) to `1` (all AV). Human drivers may slow randomly; AVs follow deterministic collision-free rules according to the selected controller. The command prints the configuration and summary metrics as JSON. With `--csv`, it also writes one row per post-warm-up step. `outputs/` is ignored by Git, so reported results should always include their parameters and seeds.

## Reproduce the Checkpoint 2 pilot

The pilot compares 0%, 50% and 100% AV traffic at densities 0.10, 0.20 and 0.30 using seed 7:

```powershell
python -m experiments.checkpoint2_pilot
```

This regenerates `results/checkpoint2-pilot.csv` and prints a compact table. The pilot is an initial demonstration, not the final experiment: the final analysis will use additional AV shares and repeated seeds. See [Checkpoint 2 notes](docs/checkpoint-2.md) for the model explanation, preliminary observations, limitations and next experiment.

## Run the repeated-seed steady-state baseline

The steady-state baseline expands the comparison to 0%, 10%, 25%, 50%, 75% and 100% AV traffic at each pilot density. By default it runs seeds 1 through 20 and writes both individual-run results and summaries across seeds:

```powershell
python -m experiments.final_experiment
```

Use `--seeds` to select another reproducible set, including inclusive ranges:

```powershell
python -m experiments.final_experiment --seeds 1-30
```

`results/final-runs.csv` contains one row per independent simulation. `results/final-summary.csv` reports the mean and sample standard deviation across seeds for each density and AV share. The across-seed variation is distinct from `speed_std`, which measures variation among vehicle-speed observations within one simulation.

## Run the controlled braking experiment

The shock-recovery experiment introduces the same eight-step braking event into
each run, then measures the severity of the disruption and the time required for
traffic to recover. It compares one- and two-lane roads, reactive and
anticipatory control, densities 0.20 and 0.30, and 0%, 25%, 50%, 75% and 100%
AV share across seeds 1 through 10:

```powershell
python -m experiments.shock_recovery
```

Two-lane conditions use twice as many vehicles as their one-lane counterparts,
so occupancy density remains `vehicles / (road length * lanes)`. This isolates
the effect of access to a passing lane from a change in road occupancy. Use
`--lanes 1`, `--lanes 2` or `--lanes all` and `--policy reactive`,
`--policy anticipatory` or `--policy all` to run a subset of the matrix.

The disturbance begins at measurement step 100, after a 200-step warm-up, and
caps vehicle 0 at speed zero through step 107. Recovery is the first 20-step
post-event window whose mean speed reaches at least 95% of the pre-event mean.
The command writes:

- `results/shock-recovery-timeseries.csv`: per-step metrics for representative
  seed 1 at every density and AV share;
- `results/shock-recovery-runs.csv`: one row of disruption and recovery metrics
  per independent run, including its matched no-shock control and control-relative
  effects; and
- `results/shock-recovery-summary.csv`: means and sample standard deviations
  across seeds for each condition.

Generate the report-ready quantitative and qualitative figures after producing
the shock-recovery CSV files:

```powershell
python -m experiments.generate_figures
```

This writes three dependency-free SVG files under `results/figures/`: a summary
comparison of braking severity and recovery time, representative recovery
curves, and a space-time comparison showing individual vehicle trajectories.
The trajectory recorder is opt-in, so normal experiment runs retain their
existing compact outputs. SVG is used so labels and paths remain sharp when
inserted into the report or demonstration slides.

The base command also supports a single disturbed run:

```powershell
python -m traffic_sim --vehicles 120 --lanes 2 --av-share 0.5 --av-policy anticipatory --warmup 200 --steps 400 --seed 7 --disturbance-start-step 100 --disturbance-duration 8 --disturbance-vehicle-id 0 --disturbance-speed-cap 0
```

This braking event is a controlled model intervention used to compare traffic
resilience. It is not intended to reproduce a particular real-world incident.
Each disturbed run is paired with an identical no-shock run using the same
configuration, initial state and random seed. The run output records a stable
pair identifier, the disturbed vehicle type and starting lane, and differences
from the matched control. This separates normal stochastic variation from the
effect attributed to the braking intervention.

## Run the statistical comparison

After generating the shock-recovery runs, calculate treatment effects and 95%
confidence intervals with:

```powershell
python -m experiments.statistical_analysis
```

`results/statistical-effects.csv` reports within-seed effects relative to the
0% AV condition, reactive control, the equivalent one-lane condition and each
run's matched no-shock control. Shock summaries also report recovery rate,
median and interquartile range so runs that do not recover are visible rather
than silently discarded.

## Run the robustness experiment

Test whether the conclusions change with braking duration, recovery threshold
or warm-up length using a bounded set of representative conditions:

```powershell
python -m experiments.robustness
```

The command writes `results/robustness-runs.csv` and
`results/robustness-summary.csv`. Recovery thresholds are evaluated from the
same simulated trajectory, avoiding unnecessary duplicate runs. The default
matrix uses five seeds and is intended to test the robustness of the main
conclusion rather than replace the final experiment.

## Two-person workflow

We use small GitHub issues and pull requests so each member owns a substantive part of the model and reviews the other's work. The morning member starts the human-only baseline and verification. The evening member reviews the baseline, proposes and implements AV behaviour, then suggests the next morning task based on pilot results. Work passes back for experiments, analysis and interpretation. Both members contribute to modelling decisions, the report and the demonstration.

At each handoff, leave a GitHub issue or PR update with what changed, the commands run, any open question, and the next task. Record modelling decisions in docs/model-spec.md so they do not depend on chat history.

The official submission deadline is Friday 9 October 2026 at 11:59 pm. Checkpoint 2 is the next immediate discussion with the facilitator; confirm its exact scheduled time from the unit information.
