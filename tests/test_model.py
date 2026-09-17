import unittest

from traffic_sim import SimulationConfig, TrafficModel, Vehicle, run_simulation


class TrafficModelTests(unittest.TestCase):
    def test_gap_wraps_across_end_of_road(self):
        config = SimulationConfig(
            road_length=10, num_vehicles=2, max_speed=5, human_slow_probability=0
        )
        model = TrafficModel(config)
        model.vehicles = [Vehicle(0, 9, 1), Vehicle(1, 2, 0)]

        vehicles = model.step()

        self.assertEqual(vehicles[0], Vehicle(0, 1, 2))
        self.assertEqual(vehicles[1], Vehicle(1, 3, 1))

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


if __name__ == "__main__":
    unittest.main()
