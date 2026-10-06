import unittest

from traffic_sim import SimulationConfig, TrafficModel, Vehicle, run_simulation


class TrafficModelTests(unittest.TestCase):
    def test_gap_wraps_across_end_of_road(self):
        config = SimulationConfig(
            road_length=10, num_vehicles=2, max_speed=5, human_slow_probability=0
        )
        model = TrafficModel(config)
        # Explicitly set vehicle_type to match our updated dataclass signature
        model.vehicles = [Vehicle(0, 9, 1, "human"), Vehicle(1, 2, 0, "human")]

        vehicles = model.step()

        # Update assertions to include the vehicle_type field
        self.assertEqual(vehicles[0], Vehicle(0, 1, 2, "human"))
        self.assertEqual(vehicles[1], Vehicle(1, 3, 1, "human"))

    def test_random_slowing_extreme_prevents_single_car_from_starting(self):
        config = SimulationConfig(
            road_length=10, num_vehicles=1, max_speed=5, human_slow_probability=1
        )
        model = TrafficModel(config)
        initial_position = model.vehicles[0].position
        for _ in range(10):
            self.assertEqual(model.step()[0].position, initial_position)

    def test_no_collisions_or_invalid_state_during_run(self):
        config = SimulationConfig(seed=42, num_vehicles=60)
        model = TrafficModel(config)
        for _ in range(500):
            vehicles = model.step()
            self.assertEqual(len(vehicles), 60)
            self.assertEqual(len({vehicle.position for vehicle in vehicles}), 60)
            self.assertTrue(all(0 <= vehicle.speed <= config.max_speed for vehicle in vehicles))

    def test_same_seed_reproduces_measurements(self):
        config = SimulationConfig(seed=17)
        self.assertEqual(
            run_simulation(config, steps=30, warmup=10),
            run_simulation(config, steps=30, warmup=10),
        )

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            SimulationConfig(road_length=10, num_vehicles=11)
        with self.assertRaises(ValueError):
            SimulationConfig(human_slow_probability=1.1)

    def test_zero_av_share_is_human_only(self):
        config = SimulationConfig(road_length=20, num_vehicles=10, av_share=0.0)
        model = TrafficModel(config)
        self.assertTrue(all(v.vehicle_type == "human" for v in model.vehicles))

    def test_mixed_traffic_contains_human_and_av_vehicles(self):
        config = SimulationConfig(road_length=20, num_vehicles=10, av_share=0.5, seed=42)
        model = TrafficModel(config)
        types = {v.vehicle_type for v in model.vehicles}
        self.assertEqual(types, {"human", "av"})

    def test_all_autonomous_configuration(self):
        config = SimulationConfig(road_length=20, num_vehicles=10, av_share=1.0)
        model = TrafficModel(config)
        self.assertTrue(all(v.vehicle_type == "av" for v in model.vehicles))

    def test_invalid_share_bounds_rejected(self):
        with self.assertRaises(ValueError):
            SimulationConfig(av_share=-0.1)
        with self.assertRaises(ValueError):
            SimulationConfig(av_share=1.1)

    def test_invalid_speed_caps_are_rejected(self):
        config = SimulationConfig(road_length=20, num_vehicles=2)
        model = TrafficModel(config)

        with self.assertRaisesRegex(ValueError, "unknown vehicle"):
            model.step(speed_caps={99: 0})
        with self.assertRaisesRegex(ValueError, "between 0 and max_speed"):
            model.step(speed_caps={0: -1})
        with self.assertRaisesRegex(ValueError, "between 0 and max_speed"):
            model.step(speed_caps={0: config.max_speed + 1})

    def test_vehicles_cannot_overtake_or_swap_order(self):
        """Regression test for tracking order bug."""
        config = SimulationConfig(road_length=20, num_vehicles=2, max_speed=5, human_slow_probability=0)
        model = TrafficModel(config)
        model.vehicles = [Vehicle(0, 5, 4, "human"), Vehicle(1, 7, 0, "human")]
        
        for _ in range(5):
            model.step()
            car_0 = next(v for v in model.vehicles if v.vehicle_id == 0)
            car_1 = next(v for v in model.vehicles if v.vehicle_id == 1)
            self.assertTrue(car_0.position < car_1.position or car_0.position > 15)

    def test_two_lane_vehicles_can_switch_lanes_safely(self) -> None:
        """Confirms that a vehicle switches lanes when blocked by a slow car ahead."""
        config = SimulationConfig(road_length=20, num_vehicles=2, lanes=2, av_share=0.0)
        model = TrafficModel(config)
        
        from traffic_sim.model import Vehicle
        # Place vehicle 0 directly behind vehicle 1 in the slow lane (lane 0)
        model.vehicles = [Vehicle(0, 5, 4, "human", 0), Vehicle(1, 6, 0, "human", 0)]
        
        updated_vehicles = model.step()
        # The trailing car must dynamically hop over to the fast lane (lane 1)
        self.assertEqual(updated_vehicles[0].lane, 1)

    def test_occupied_target_cell_blocks_lane_change_at_wraparound(self):
        config = SimulationConfig(
            road_length=10,
            num_vehicles=3,
            max_speed=5,
            human_slow_probability=0,
            lanes=2,
        )
        model = TrafficModel(config)
        model.vehicles = [
            Vehicle(0, 9, 3, "human", 0),
            Vehicle(1, 0, 0, "human", 0),
            Vehicle(2, 9, 0, "human", 1),
        ]

        vehicles = model.step()
        trailing = next(vehicle for vehicle in vehicles if vehicle.vehicle_id == 0)

        self.assertEqual(trailing.lane, 0)
        self.assertEqual(len({(vehicle.lane, vehicle.position) for vehicle in vehicles}), 3)

    def test_fast_rear_vehicle_blocks_unsafe_lane_change(self):
        config = SimulationConfig(
            road_length=20,
            num_vehicles=4,
            max_speed=5,
            human_slow_probability=0,
            lanes=2,
        )
        model = TrafficModel(config)
        model.vehicles = [
            Vehicle(0, 5, 4, "human", 0),
            Vehicle(1, 6, 0, "human", 0),
            Vehicle(2, 3, 3, "human", 1),
            Vehicle(3, 15, 0, "human", 1),
        ]

        vehicles = model.step()
        blocked_vehicle = next(
            vehicle for vehicle in vehicles if vehicle.vehicle_id == 0
        )

        self.assertEqual(blocked_vehicle.lane, 0)
        self.assertEqual(
            len({(vehicle.lane, vehicle.position) for vehicle in vehicles}),
            config.num_vehicles,
        )

    def test_two_lane_run_is_reproducible(self):
        config = SimulationConfig(
            road_length=50,
            num_vehicles=30,
            human_slow_probability=0.3,
            av_share=0.5,
            av_policy="anticipatory",
            lanes=2,
            seed=19,
        )

        self.assertEqual(
            run_simulation(config, warmup=20, steps=50),
            run_simulation(config, warmup=20, steps=50),
        )

    def test_high_density_two_lane_runs_preserve_invariants_across_seeds(self):
        for seed in range(1, 11):
            config = SimulationConfig(
                road_length=30,
                num_vehicles=48,
                human_slow_probability=0.4,
                av_share=0.5,
                av_policy="anticipatory",
                lanes=2,
                seed=seed,
            )
            model = TrafficModel(config)
            expected_ids = {vehicle.vehicle_id for vehicle in model.vehicles}

            for _ in range(100):
                vehicles = model.step()
                self.assertEqual(len(vehicles), config.num_vehicles)
                self.assertEqual(
                    {vehicle.vehicle_id for vehicle in vehicles}, expected_ids
                )
                self.assertEqual(
                    len({(vehicle.lane, vehicle.position) for vehicle in vehicles}),
                    config.num_vehicles,
                )
                self.assertTrue(
                    all(0 <= vehicle.speed <= config.max_speed for vehicle in vehicles)
                )

if __name__ == "__main__":
    unittest.main()
