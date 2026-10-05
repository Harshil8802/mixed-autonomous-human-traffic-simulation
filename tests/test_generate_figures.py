import tempfile
import unittest
from pathlib import Path

from experiments.generate_figures import create_summary_figure
from traffic_sim import SimulationConfig, run_simulation


class TrajectoryRecordingTests(unittest.TestCase):
    def test_trajectory_recording_is_optional_and_complete(self):
        config = SimulationConfig(road_length=20, num_vehicles=4, seed=3)

        ordinary = run_simulation(config, warmup=2, steps=5)
        recorded = run_simulation(
            config, warmup=2, steps=5, record_trajectories=True
        )

        self.assertEqual(ordinary["trajectories"], [])
        self.assertEqual(len(recorded["trajectories"]), 20)
        self.assertEqual(ordinary["summary"], recorded["summary"])
        self.assertEqual(ordinary["per_step"], recorded["per_step"])
        self.assertEqual(
            {row["vehicle_id"] for row in recorded["trajectories"]},
            {0, 1, 2, 3},
        )


class SummaryFigureTests(unittest.TestCase):
    def test_summary_figure_is_valid_svg_with_both_metrics(self):
        rows = []
        for lanes in (1, 2):
            for policy in ("reactive", "anticipatory"):
                for share in (0.0, 0.5, 1.0):
                    rows.append(
                        {
                            "lanes": str(lanes),
                            "density": "0.3",
                            "requested_av_share": str(share),
                            "av_policy": policy,
                            "maximum_stopped_fraction_after_braking_mean": str(0.5 - 0.2 * share),
                            "recovery_time_steps_mean": str(40 - 10 * share),
                        }
                    )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "summary.svg"
            create_summary_figure(rows, output)
            content = output.read_text(encoding="utf-8")

        self.assertIn("<svg", content)
        self.assertIn("Maximum stopped fraction", content)
        self.assertIn("Recovery time (steps)", content)
        self.assertTrue(content.rstrip().endswith("</svg>"))


if __name__ == "__main__":
    unittest.main()
