import argparse
import unittest

from experiments.final_experiment import (
    aggregate_runs,
    parse_seeds,
    run_experiment,
)


class FinalExperimentTests(unittest.TestCase):
    def test_parse_seeds_accepts_lists_ranges_and_removes_duplicates(self):
        self.assertEqual(parse_seeds("1-3,5,3"), [1, 2, 3, 5])

    def test_parse_seeds_rejects_descending_range(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_seeds("5-2")

    def test_small_experiment_covers_every_condition(self):
        rows = run_experiment(
            [1, 2],
            road_length=10,
            vehicle_counts=(2,),
            av_shares=(0.0, 1.0),
            max_speed=3,
            warmup=2,
            steps=4,
        )

        self.assertEqual(len(rows), 4)
        self.assertEqual({row["seed"] for row in rows}, {1, 2})
        self.assertEqual({row["requested_av_share"] for row in rows}, {0.0, 1.0})

    def test_aggregation_reports_seed_variation_separately(self):
        rows = [
            {
                "density": 0.2,
                "num_vehicles": 40,
                "requested_av_share": 0.5,
                "realised_av_share": 0.5,
                "mean_speed": 2.0,
                "stopped_fraction": 0.2,
                "speed_std": 1.0,
            },
            {
                "density": 0.2,
                "num_vehicles": 40,
                "requested_av_share": 0.5,
                "realised_av_share": 0.5,
                "mean_speed": 4.0,
                "stopped_fraction": 0.1,
                "speed_std": 2.0,
            },
        ]

        summary = aggregate_runs(rows)[0]

        self.assertEqual(summary["num_runs"], 2)
        self.assertEqual(summary["mean_speed_mean"], 3.0)
        self.assertAlmostEqual(summary["mean_speed_seed_sd"], 2 ** 0.5)
        self.assertAlmostEqual(summary["stopped_fraction_mean"], 0.15)


if __name__ == "__main__":
    unittest.main()
