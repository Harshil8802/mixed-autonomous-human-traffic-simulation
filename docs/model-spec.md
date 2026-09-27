# Draft model specification

**Status:** Core baseline and mixed-traffic model rules implemented and verified for Checkpoint 2. Parameters below are pilot choices, not calibrated real-world values.

## Research question

How does autonomous vehicle proportion affect stop-and-go traffic stability at different traffic densities on a single-lane circular road?

We will test whether adding AVs changes mean speed and traffic stability, whether the effect depends on density, and whether any apparent improvement is gradual or concentrated in a narrower range of AV shares. A threshold is a possible result, not an assumption.

## Road and vehicle state

- The road is a ring of `L` discrete cells. Each vehicle occupies one cell.
- At time `t`, vehicle `i` has an integer position `x_i`, integer speed `v_i` in `0..v_max`, and type `human` or `av`.
- Density is `N/L`, where `N` is the fixed number of vehicles. There are no entries or exits.
- The gap `g_i` is the number of empty cells before the next vehicle ahead, wrapping around the ring.
- Every vehicle decides from the same time-`t` snapshot; all positions change together. This synchronous update prevents vehicle-order artifacts.

## Proposed one-step update

1. Accelerate: `v_i = min(v_i + 1, v_max)`.
2. Keep a collision-free gap: `v_i = min(v_i, g_i)`.
3. For a human driver, reduce speed by one with probability `p_h`, stopping at zero.
4. For the implemented AV rule, vehicles use the same acceleration and gap rules but completely bypass the random slowing rule ($p_{av} = 0.0$). This provides a controlled behavioural contrast rather than a claim about actual automated driving dynamics. The model does not currently represent sensing uncertainty or reaction delays.
5. Move: `x_i = (x_i + v_i) mod L`.

The first implementation should support human-only traffic. AV behaviour is a separate contribution after the baseline is checked. Explicit reaction delay, AV communication and lane changes are outside the initial scope.

## Pilot experiment design

- Initial road length: `L = 200` cells; initial maximum speed: `v_max = 5` cells per step.
- Pilot densities: `N = 20, 40, 60` vehicles (density `0.10, 0.20, 0.30`). These may change if pilots do not produce informative conditions.
- AV shares: `0%, 10%, 25%, 50%, 75%, 100%`. For a fixed `N`, the AV count is rounded to the nearest integer (`round(N * av_share)`), shuffled randomly across initial vehicle positions, and both the requested and actual realized shares are locked into the output logs to ensure strict execution tracking.
- Hold road length, maximum speed, human slowing probability, simulation length and initialization method constant within a comparison.
- Run multiple independent seeds per condition. Use a small pilot first, then choose enough repeats to show variation in final results.
- Proposed analysis window: discard an initial settling period, then measure over the remaining steps. Specify the final step counts before running reported experiments.

## Measurements

- **Mean speed:** average `v_i` over all vehicles and measurement steps.
- **Stopped fraction:** proportion of vehicle observations with `v_i = 0` during measurement.
- **Speed variation:** standard deviation of individual speeds over the measurement window. Also plot the mean speed over time to reveal fluctuations.
- **Qualitative evidence:** a space-time diagram of vehicle positions, with selected vehicle speeds or stopped positions marked, to inspect backward-moving congestion waves.
- **Optional throughput:** count vehicles crossing a fixed road cell per time step, handling wraparound correctly.

Report means and variation across runs. Record each run's parameters and seed so figures can be regenerated. If a sharp change appears, sample additional AV shares around it before making a threshold claim.

## Verification before interpreting results

- Vehicle positions are unique at every step; no collisions occur.
- Vehicle count stays fixed and positions and speeds stay within their valid ranges.
- A run with the same configuration and seed reproduces the same output.
- The human-only and AV-only extremes run successfully.
- Inspect simple hand-calculated cases, including a gap across the ring boundary.
- Compare qualitative plots across free-flow and congested pilot conditions.

## Decisions for both members

1. Confirm or revise the update rule and `p_h` pilot value. Random slowing and explicit reaction delay are different assumptions; the first version uses random slowing only.
2. Agree how vehicles are placed and typed initially, and whether identical starting positions should be reused across AV-share comparisons.
3. Finalize run length, settling period, repeat count and exact plot conventions after pilot results.
4. Ask the facilitator whether this focused single-lane model provides enough scope when supported by systematic experiments and a sensitivity study.

Any conclusion must be framed as conditional on these rules and parameters. We should discuss how the chosen AV rule itself influences the result, and test a plausible alternative or sensitivity if time allows.

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
planned anticipatory-controller comparison will test whether an alternative AV
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


### Night Shift Updates (Issue #14 Two-Lane Implementation)

- **Two-Lane Topology Upgrade:** Extended the `SimulationConfig` and `TrafficModel` core framework to map vehicle positions across a parallel two-lane ring track layout (\(\text{lanes} \in \{1, 2\}\)).
- **Symmetric Passing Rules:** Integrated local lane-changing look-ahead and look-back lookups into the synchronous `step()` phase. Vehicles will dynamically toggle to the adjacent lane before moving forward if the target position is clear, the target path provides a wider forward clearance gap, and the trailing vehicle safety margins prevent collisions.
- **Verification Gates:** Restructured system position checks (`_check_state`) to validate coordinates as independent `(lane, position)` unique tracking pairs, unblocking cross-lane vehicles while successfully preventing local vehicle overlap bugs.
