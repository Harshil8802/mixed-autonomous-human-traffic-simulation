# Mixed Human and Autonomous Traffic Simulation

CITS4403 group research project investigating how the share of autonomous vehicles affects stop-and-go traffic on a single-lane circular road. The project is completed by two students. The model, experiments, report and demonstration should answer the same research question and be reproducible from the submitted code.

## Draft research question

How does autonomous vehicle proportion affect traffic stability at different traffic densities in a simplified mixed-traffic model?

This question and the model rules are working proposals for discussion with the teammate and facilitator. The model does not claim to predict real-road AV performance.

## Initial scope

- One lane on a circular road; no intersections, entry, exits or lane changes.
- Human and AV vehicles follow explicit, documented update rules.
- Start with a human-only baseline, then add AV behaviour.
- Compare several AV shares at several densities using repeated runs and recorded random seeds.
- Report average speed, stopped-vehicle fraction and speed variation; inspect space-time plots for traffic waves.

See [draft model specification](docs/model-spec.md) for assumptions, proposed measurements and decisions still to make.

## Run the human-only baseline

Python 3 with the standard library is sufficient. From the repository root:

```powershell
python -m traffic_sim --road-length 200 --vehicles 40 --max-speed 5 --human-slow-prob 0.2 --warmup 200 --steps 800 --seed 7 --csv outputs/baseline-seed7.csv
python -m unittest discover -s tests -v
```

The command prints the run configuration and summary metrics as JSON. With `--csv`, it also writes one row of measurements per post-warm-up step. `outputs/` is ignored by Git; results used in the report should be regenerated from recorded commands and seeds. The implementation currently supports human-driven vehicles only. The AV rule is the evening member's separate task.

## Two-person workflow

We use small GitHub issues and pull requests so each member owns a substantive part of the model and reviews the other's work. The morning member starts the human-only baseline and verification. The evening member reviews the baseline, proposes and implements AV behaviour, then suggests the next morning task based on pilot results. Work passes back for experiments, analysis and interpretation. Both members contribute to modelling decisions, the report and the demonstration.

At each handoff, leave a GitHub issue or PR update with what changed, the commands run, any open question, and the next task. Record modelling decisions in docs/model-spec.md so they do not depend on chat history.

The official submission deadline is Friday 9 October 2026 at 11:59 pm. Checkpoint 2 is the next immediate discussion with the facilitator; confirm its exact scheduled time from the unit information.
