import unittest
from experiments.shock_recovery import (
    aggregate_runs,
    calculate_recovery_metrics,
    run_shock_experiment,
)
from traffic_sim import BrakingDisturbance, SimulationConfig, TrafficModel, run_simulation


class BrakingDisturbanceTests(unittest.TestCase):
    def test_no_speed_cap_preserves_existing_step_sequence(self):
        config = SimulationConfig(
            road_length=30,
            num_vehicles=8,
            human_slow_probability=0.2,
            av_share=0.5,
            seed=9,
        )
        baseline = TrafficModel(config)
        explicit_none = TrafficModel(config)

        for _ in range(20):
            self.assertEqual(baseline.step(), explicit_none.step(speed_caps=None))

    def test_disturbance_is_active_for_exact_configured_window(self):
        config = SimulationConfig(
            road_length=20,
            num_vehicles=4,
            max_speed=3,
            human_slow_probability=0,
            seed=2,
        )
        disturbance = BrakingDisturbance(
            vehicle_id=0,
            start_step=2,
            duration=2,
            speed_cap=0,
        )

        result = run_simulation(
            config,
            warmup=0,
            steps=5,
            disturbance=disturbance,
        )

        self.assertEqual(
            [row["disturbance_active"] for row in result["per_step"]],
            [False, True, True, False, False],
        )
        active_rows = [row for row in result["per_step"] if row["disturbance_active"]]
        self.assertTrue(all(row["disturbed_vehicle_speed"] == 0 for row in active_rows))

    def test_repeated_braking_remains_collision_free(self):
        config = SimulationConfig(
            road_length=50,
            num_vehicles=20,
            human_slow_probability=0.2,
            av_share=0.5,
            seed=4,
        )
        model = TrafficModel(config)

        for step in range(50):
            caps = {0: 0} if 10 <= step < 18 else None
            vehicles = model.step(speed_caps=caps)
            self.assertEqual(
                len({vehicle.position for vehicle in vehicles}),
                config.num_vehicles,
            )

    def test_disturbance_must_finish_within_measurement_period(self):
        config = SimulationConfig(road_length=20, num_vehicles=4)
        disturbance = BrakingDisturbance(start_step=4, duration=3)

        with self.assertRaises(ValueError):
            run_simulation(config, steps=5, disturbance=disturbance)


class RecoveryMetricTests(unittest.TestCase):
    def test_recovery_uses_sustained_post_event_window(self):
        rows = [
            {"step": 1, "mean_speed": 4.0, "stopped_fraction": 0.0},
            {"step": 2, "mean_speed": 4.0, "stopped_fraction": 0.0},
            {"step": 3, "mean_speed": 0.0, "stopped_fraction": 1.0},
            {"step": 4, "mean_speed": 0.0, "stopped_fraction": 0.8},
            {"step": 5, "mean_speed": 2.0, "stopped_fraction": 0.4},
            {"step": 6, "mean_speed": 4.0, "stopped_fraction": 0.0},
            {"step": 7, "mean_speed": 4.0, "stopped_fraction": 0.0},
        ]
        disturbance = BrakingDisturbance(start_step=3, duration=2)

        metrics = calculate_recovery_metrics(
            rows,
            disturbance,
            recovery_window=2,
        )

        self.assertEqual(metrics["pre_disturbance_mean_speed"], 4.0)
        self.assertEqual(metrics["minimum_mean_speed_after_braking"], 0.0)
        self.assertEqual(metrics["maximum_stopped_fraction_after_braking"], 1.0)
        self.assertTrue(metrics["recovered"])
        self.assertEqual(metrics["recovery_time_steps"], 3)

    def test_small_experiment_covers_requested_conditions(self):
        # FIX A: Use a short custom disturbance so short 8-step tests don't throw step bounds exceptions
        disturbance = BrakingDisturbance(start_step=2, duration=2)

        timeseries, runs = run_shock_experiment(
            seeds=(1, 2),
            road_length=20,
            vehicle_counts=(4,),
            av_shares=(0.0, 1.0),
            warmup=2,
            steps=8,
            disturbance=disturbance,
            recovery_window=2,
        )
        summaries = aggregate_runs(runs)

        # FIX B: Adjust run count to 6 (2 seeds for 0% reactive control + 4 runs for 100% split over both policies)
        self.assertEqual(len(runs), 6)
        self.assertEqual(len(summaries), 3)
        self.assertEqual({row["seed"] for row in runs}, {1, 2})
        self.assertEqual({row["requested_av_share"] for row in runs}, {0.0, 1.0})
        self.assertTrue(all(row["lanes"] == 1 for row in runs))
        self.assertTrue(all(row["num_runs"] == 2 for row in summaries))

    def test_lane_comparison_preserves_occupancy_density(self):
        disturbance = BrakingDisturbance(start_step=2, duration=2)

        timeseries, runs = run_shock_experiment(
            seeds=(1,),
            road_length=20,
            vehicle_counts=(4,),
            lane_counts=(1, 2),
            av_shares=(0.0,),
            warmup=2,
            steps=8,
            disturbance=disturbance,
            recovery_window=2,
        )
        summaries = aggregate_runs(runs)

        self.assertEqual({row["lanes"] for row in runs}, {1, 2})
        self.assertEqual(
            {(row["lanes"], row["num_vehicles"]) for row in runs},
            {(1, 4), (2, 8)},
        )
        self.assertEqual({row["density"] for row in runs}, {0.2})
        self.assertEqual({row["road_cells"] for row in runs}, {20, 40})
        self.assertEqual(len(summaries), 2)
        self.assertEqual({row["lanes"] for row in timeseries}, {1, 2})

    def test_policy_subset_keeps_all_human_control(self):
        disturbance = BrakingDisturbance(start_step=2, duration=2)

        _, runs = run_shock_experiment(
            seeds=(1,),
            road_length=20,
            vehicle_counts=(4,),
            lane_counts=(1,),
            av_shares=(0.0, 0.5),
            policies=("anticipatory",),
            warmup=2,
            steps=8,
            disturbance=disturbance,
            recovery_window=2,
        )

        self.assertEqual(
            {(row["requested_av_share"], row["av_policy"]) for row in runs},
            {(0.0, "reactive"), (0.5, "anticipatory")},
        )


class TestAnticipatoryShockRecovery(unittest.TestCase):
    def test_anticipatory_policy_option_is_accepted(self) -> None:
        """Verifies that the model correctly initializes with the anticipatory policy."""
        config = SimulationConfig(road_length=200, num_vehicles=40, av_share=0.5, av_policy="anticipatory")
        model = TrafficModel(config)
        self.assertEqual(model.config.av_policy, "anticipatory")

    def test_experiment_runner_handles_both_policies(self) -> None:
        """Ensures the shock runner processes both policies across seeds cleanly."""
        short_disturbance = BrakingDisturbance(start_step=2, duration=2)
        timeseries, runs = run_shock_experiment(
            (1,),
            road_length=20,
            vehicle_counts=(4,),
            av_shares=(0.5,),
            warmup=2,
            steps=8,
            disturbance=short_disturbance,
            recovery_window=2,
        )
        policies_logged = {row["av_policy"] for row in runs}
        self.assertTrue("reactive" in policies_logged)
        self.assertTrue("anticipatory" in policies_logged)

if __name__ == "__main__":
    unittest.main()
