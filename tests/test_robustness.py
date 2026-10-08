import unittest

from experiments.robustness import aggregate_robustness, run_robustness_experiment


class RobustnessExperimentTests(unittest.TestCase):
    def test_small_matrix_records_every_analysis_choice(self):
        rows = run_robustness_experiment(
            seeds=(1,),
            scenarios=((1, 0.5, "anticipatory"),),
            braking_durations=(1, 2),
            recovery_fractions=(0.9, 0.95),
            warmups=(0,),
            road_length=20,
            single_lane_vehicle_count=4,
            steps=8,
            disturbance_start=2,
            recovery_window=2,
        )

        self.assertEqual(len(rows), 4)
        self.assertEqual({row["braking_duration"] for row in rows}, {1, 2})
        self.assertEqual(
            {row["recovery_fraction"] for row in rows}, {0.9, 0.95}
        )
        self.assertTrue(all(row["warmup"] == 0 for row in rows))
        self.assertTrue(
            all("maximum_stopped_fraction_delta_from_control" in row for row in rows)
        )

        summaries = aggregate_robustness(rows)
        self.assertEqual(len(summaries), 4)
        self.assertTrue(all(row["num_runs"] == 1 for row in summaries))


if __name__ == "__main__":
    unittest.main()
