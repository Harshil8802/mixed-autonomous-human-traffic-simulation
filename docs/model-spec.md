# Model specification and research contribution

**Status:** The human/AV baseline, reactive and anticipatory controllers, controlled braking intervention and two-lane passing rules are implemented. The final experiment and visual analysis are being consolidated. Parameters are modelling choices rather than calibrated real-world values.

## Research question

**How do autonomous-vehicle penetration and controller strategy affect the severity and recovery of braking-induced congestion, and how does safe two-lane passing alter this response?**

The investigation tests whether increasing AV penetration changes the size and duration of a controlled traffic disruption, whether reactive and anticipatory AV rules produce different outcomes, and whether access to a second lane changes those conclusions. Human slowdown probability is varied separately as a robustness check. Any threshold or improvement is treated as an empirical result of the stated model, not an assumption.

## Originality and relationship to the taught model

The single-lane circular cellular-automaton model is a teaching baseline and is not claimed as an original model. It provides a simple, auditable control case. The team's contribution is the experimental framework built around that baseline:

1. mixed populations of stochastic human drivers and deterministic AVs;
2. comparison of reactive and anticipatory AV controller assumptions;
3. a controlled braking intervention with disruption and sustained-recovery measures;
4. a two-lane extension with explicit forward and rear safety checks for passing; and
5. repeated-seed and human-behaviour sensitivity analyses.

Together these extensions investigate traffic **resilience** rather than merely reproducing spontaneous congestion. Conclusions are conditional on the simplified rules and are not predictions about deployed autonomous vehicles.

## Road and vehicle state

- The road contains `K` parallel circular lanes of `L` discrete cells, where `K` is 1 or 2. Each vehicle occupies one `(lane, position)` cell.
- At time `t`, vehicle `i` has lane `y_i`, integer position `x_i`, integer speed `v_i` in `0..v_max`, and type `human` or `av`.
- Occupancy density is `N/(L*K)`, where `N` is the fixed number of vehicles. There are no entries or exits.
- The forward gap `g_i` is the number of empty cells before the next vehicle in the same lane, wrapping around the ring.
- Every vehicle decides from the same time-`t` snapshot; all positions change together. This synchronous update prevents vehicle-order artifacts.

## One-step update

1. **Lane-change decision (`K = 2` only):** a vehicle may move to the adjacent lane when its target cell is empty, the target lane has a larger forward gap, and the rear safety check shows that the trailing target-lane vehicle cannot reach the merge cell. Lane choices use the same pre-change snapshot.
2. **Acceleration and collision-free braking:** start from `min(v_i + 1, v_max, g_i)`.
3. **Human rule:** reduce the resulting speed by one with probability `p_h`, stopping at zero.
4. **Reactive AV rule:** use the acceleration and gap result without random slowing.
5. **Anticipatory AV rule:** also consider the leading vehicle's speed and a two-cell safety buffer, limiting acceleration more strongly when the gap is small.
6. **Optional intervention:** while a braking disturbance is active, cap the selected vehicle's speed after its ordinary controller update.
7. **Movement:** update every vehicle simultaneously using `x_i = (x_i + v_i) mod L`.

Human drivers and both AV policies use the same collision-free gap constraint. The model excludes intersections, entry and exit, heterogeneous vehicle lengths, sensing error, explicit reaction delay and AV communication.

## Experimental strategy

- Use `L = 200` cells per lane and `v_max = 5` cells per step.
- Compare occupancy densities while accounting for lane count with `N/(L*K)`. Equal-density one- and two-lane comparisons therefore use different vehicle counts.
- Compare AV shares of `0%, 25%, 50%, 75%, 100%`; the steady-state baseline additionally samples `10%`.
- For a fixed `N`, calculate `round(N * av_share)`, shuffle vehicle types reproducibly and record both requested and realised shares.
- Compare reactive and anticipatory policies. The 0% AV condition is shared because AV policy cannot affect an all-human population.
- Hold maximum speed, human slowdown probability, warm-up, measurement duration, intervention and initialisation method constant within each comparison.
- Repeat every reported condition across recorded seeds and report variation across runs.
- Use the human slowdown sweep as a robustness analysis rather than as a separate research question.

## Measurements

- **Mean speed:** average `v_i` over all vehicles and measurement steps.
- **Stopped fraction:** proportion of vehicle observations with `v_i = 0` during measurement.
- **Speed variation:** standard deviation of individual speeds over the measurement window. Also plot the mean speed over time to reveal fluctuations.
- **Qualitative evidence:** a space-time diagram of vehicle positions, with selected vehicle speeds or stopped positions marked, to inspect backward-moving congestion waves.
- **Traffic flow:** occupancy density multiplied by mean speed.
- **Disruption severity:** minimum network mean speed and maximum stopped fraction after braking begins.
- **Recovery time:** first sustained post-disturbance window that returns to the specified fraction of pre-disturbance mean speed.

Report means and variation across runs. Record each run's parameters and seed so figures can be regenerated. If a sharp change appears, sample additional AV shares around it before making a threshold claim.

## Verification before interpreting results

- Vehicle positions are unique at every step; no collisions occur.
- Vehicle count stays fixed and positions and speeds stay within their valid ranges.
- A run with the same configuration and seed reproduces the same output.
- The human-only and AV-only extremes run successfully.
- Inspect simple hand-calculated cases, including a gap across the ring boundary.
- Compare qualitative plots across free-flow and congested pilot conditions.

## Final design decisions

1. Random slowing represents unresolved human variability; it is not an explicit reaction-delay model.
2. Initial cells are sampled without replacement, vehicle types are shuffled reproducibly, and the seed is recorded with every run.
3. The controlled braking event supplies the common intervention used to compare resilience.
4. The two AV policies are alternative modelling assumptions whose outcomes must be compared rather than treating either as realistic by default.
5. The second lane is a structural intervention. Equal-density comparisons must use `N/(L*K)` so that added capacity is not mistaken for a controller effect.

Any conclusion must be framed as conditional on these rules and parameters. We should discuss how the chosen AV rule itself influences the result, and test a plausible alternative or sensitivity if time allows.

## Reproducible qualitative evidence

The final evidence workflow records full vehicle trajectories only when
`record_trajectories=True`; routine parameter sweeps retain compact aggregate
outputs. Each trajectory row stores the measurement step, vehicle identity,
lane, position, speed and type. `python -m experiments.generate_figures` uses
this opt-in record to create space-time diagrams and representative recovery
curves, and uses the repeated-seed summary CSV to plot disruption severity and
recovery time. Figures are deterministic SVG files generated with the Python
standard library, so every report graphic can be recreated without manual
chart editing.

## Controlled braking and recovery extension

To study transient stop-and-go waves as well as steady-state averages, the model
supports an optional controlled braking event during the measurement period. A
specified vehicle receives a temporary speed cap after the ordinary acceleration,
gap and random-slowing rules have been applied. Because the cap can only reduce
the selected speed, the original collision-free gap constraint remains in force.
Runs without a disturbance use the original update rule and random-number sequence.

The initial shock-recovery experiment uses the following fixed intervention:

- warm up for 200 steps;
- begin the event at measurement step 100;
- cap vehicle 0 at speed 0 for eight steps; and
- observe the remainder of a 400-step measurement period.

The pre-disturbance reference speed is the mean of measurement steps before the
event. Recovery time is the number of steps after the event until the first
20-step rolling window reaches at least 95% of that reference. We also record
the minimum network mean speed and maximum stopped fraction after braking,
overall speed variation, and flow (`density * mean speed`). If the threshold is
not reached before the run ends, the run is reported as not recovered rather
than assigning an artificial recovery time.

This intervention provides a reproducible comparison of resilience under the
model assumptions. It does not represent calibrated emergency braking, human
reaction time, or a specific road incident.

### Initial reactive-controller observations

Across 10 seeds, every tested run recovered within the 400-step measurement
period. Increasing AV share reduced the average maximum stopped fraction after
braking at both densities: from 40.0% to 20.8% at density 0.20 and from 50.0%
to 20.0% at density 0.30. Recovery time was not monotonic at density 0.20: it
fell from 44.5 steps at 0% AV to 33.4 at 50% AV, then rose to 41.0 at 100% AV.
At density 0.30 it generally declined, reaching 23.0 steps at 100% AV. These
results show why both disruption severity and recovery time must be reported;
one metric alone does not establish that a controller is more resilient. The
implemented anticipatory-controller comparison tests whether an alternative AV
rule changes this pattern.

### Evening Shift Updates (Issue #4 Implementation)

- **AV Rule Choice:** Implemented the proposed baseline where AVs use the same acceleration and gap rules but completely bypass random slowing (\(p_{av} = 0.0\)). This provides a clean empirical contrast to isolate human stochastic delays.
- **Initial Placement & Typing:** Vehicles are typed by calculating `round(N * av_share)`, shuffling the type assignments, and matching them to unique sorted positions on the ring. 
- **Physics Engine Fix:** Discovered a baseline array re-sorting bug in `step()`. Vehicles are now sorted by position *only once* during initialization to lock the spatial ring topology. This guarantees cars cannot illegally pass or phase through each other on the single-lane road.
- **Metrics Tracking:** Both `requested_av_share` and `realised_av_share` are now permanently saved to the final summary dictionaries and tracked inside every single row of the generated step-by-step CSV outputs.

### Late Shift Updates (Issue #10 Sensitivity Analysis)

- **Sensitivity Analysis Framework:** Added a dedicated module to test model behavior across varying human driver unpredictability layers (\(p_h \in \{0.0, 0.1, 0.2, 0.3, 0.4\}\)) crossed with critical AV mix thresholds (0%, 50%, 100%).
- **Statistical Aggregation over Seeds:** Expanded experiment calculations to compute mean distributions and sample standard deviations across 10 distinct seeds per layout condition block.
- **Reproduction Track:**
  ```bash
  python -m experiments.slowdown_sensitivity
  ```
- **Sensitivity Insights:**
  - **100% AV Control Stability:** Verified that when the AV penetration index reaches 1.0, varying \(p_h\) causes 0.000 variance in macro metrics (Speed holds flat at `4.000 +/- 0.000`), confirming the deterministic boundary conditions of the control setup.
  - **Damping Envelopes:** A 50% AV share scales linearly, providing continuous flow damping across all tested noise ranges—slashing stopped vehicle observations by approximately 30% even when human volatility spikes to \(p_h = 0.4\).


### Late Night Shift Updates (Issue #13 Policy Comparison)

- **Anticipatory AV Logic:** Implemented an alternative control rule using a `safety_buffer = 2`. When the gap opens up, it scales with the leader's speed; when the gap drops below the buffer, it limits acceleration to match the leading vehicle's velocity exactly.
- **Verification Matrix:** Evaluated both `reactive` and `anticipatory` modes across densities (0.20, 0.30) and all specified AV share bands over 10 independent seeds.

#### Observed Policy Trade-offs
- **Density 0.20 Behavior:** The anticipatory controller manages stop-and-go waves efficiently at medium shares. At 50% AV share, the anticipatory mode keeps the max stopped fraction lower than the reactive mode (`31.2%` vs `33.0%`). However, at 100% AV share, the defensive buffer causes a recovery drag, taking `35.4` steps to stabilize compared to reactive's lower max breakdown footprint of `20.8%`.
- **Density 0.30 Congestion:** Under heavy crowding, both policies struggle similarly with peak shock dissipation up to 75% share. At 100% AV share, reactive control outperforms anticipatory, keeping the maximum stopped fraction down to `20.0%` (compared to anticipatory's `48.3%`) and recovering faster (`23.0` steps vs `24.7` steps). This highlights that rigid safety buffers can accidentally stall grid clearance in overcrowded conditions.


### Night Shift Updates (Issue #16 Two-Lane Implementation)

- **Two-Lane Topology Upgrade:** Extended the `SimulationConfig` and `TrafficModel` core framework to map vehicle positions across a parallel two-lane ring track layout (\(\text{lanes} \in \{1, 2\}\)).
- **Symmetric Passing Rules:** Integrated local lane-changing look-ahead and look-back lookups into the synchronous `step()` phase. Vehicles will dynamically toggle to the adjacent lane before moving forward if the target position is clear, the target path provides a wider forward clearance gap, and the trailing vehicle safety margins prevent collisions.
- **Verification Gates:** Restructured system position checks (`_check_state`) to validate coordinates as independent `(lane, position)` unique tracking pairs, unblocking cross-lane vehicles while successfully preventing local vehicle overlap bugs.
