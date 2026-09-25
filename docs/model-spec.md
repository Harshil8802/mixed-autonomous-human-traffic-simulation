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