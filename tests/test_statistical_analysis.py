import unittest

from experiments.shock_recovery import _mean_ci95
from experiments.statistical_analysis import aggregate_effects, calculate_effect_rows


def make_row(
    *, lanes, share, policy, seed, maximum_stopped, recovery, control_delta
):
    return {
        "pair_id": f"{lanes}-{share}-{policy}-{seed}",
        "lanes": lanes,
        "density": 0.3,
        "requested_av_share": share,
        "av_policy": policy,
        "seed": seed,
        "maximum_stopped_fraction_after_braking": maximum_stopped,
        "recovery_time_steps": recovery,
        "maximum_stopped_fraction_delta_from_control": control_delta,
    }


class ConfidenceIntervalTests(unittest.TestCase):
    def test_t_interval_is_symmetric_around_sample_mean(self):
        low, high = _mean_ci95([1.0, 2.0, 3.0, 4.0])

        self.assertAlmostEqual((low + high) / 2, 2.5)
        self.assertLess(low, 2.5)
        self.assertGreater(high, 2.5)


class TreatmentEffectTests(unittest.TestCase):
    def test_effects_use_same_seed_reference_conditions(self):
        rows = [
            make_row(
                lanes=1,
                share=0.0,
                policy="reactive",
                seed=1,
                maximum_stopped=0.5,
                recovery=40,
                control_delta=0.2,
            ),
            make_row(
                lanes=1,
                share=0.5,
                policy="reactive",
                seed=1,
                maximum_stopped=0.4,
                recovery=30,
                control_delta=0.1,
            ),
            make_row(
                lanes=1,
                share=0.5,
                policy="anticipatory",
                seed=1,
                maximum_stopped=0.3,
                recovery=25,
                control_delta=0.05,
            ),
            make_row(
                lanes=2,
                share=0.5,
                policy="anticipatory",
                seed=1,
                maximum_stopped=0.2,
                recovery=20,
                control_delta=0.03,
            ),
        ]

        effects = calculate_effect_rows(rows)
        target = next(
            row
            for row in effects
            if row["lanes"] == 2 and row["av_policy"] == "anticipatory"
        )

        self.assertAlmostEqual(
            target[
                "maximum_stopped_fraction_after_braking_effect_vs_one_lane"
            ],
            -0.1,
        )
        self.assertEqual(target["recovery_time_steps_effect_vs_one_lane"], -5)
        self.assertEqual(
            target["maximum_stopped_effect_vs_matched_control"], 0.03
        )

        summaries = aggregate_effects(effects)
        self.assertEqual(len(summaries), 4)
        self.assertTrue(all(row["num_runs"] == 1 for row in summaries))


if __name__ == "__main__":
    unittest.main()
