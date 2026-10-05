import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.run_all import run_all


class FinalWorkflowTests(unittest.TestCase):
    def test_quick_workflow_writes_manifest_and_expected_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata_path = root / "metadata.json"
            with patch("experiments.run_all.final_experiment.DEFAULT_RAW_OUTPUT", root / "final-runs.csv"), patch(
                "experiments.run_all.final_experiment.DEFAULT_SUMMARY_OUTPUT",
                root / "final-summary.csv",
            ), patch(
                "experiments.run_all.SENSITIVITY_OUTPUT",
                root / "slowdown.csv",
            ), patch(
                "experiments.run_all.shock_recovery.DEFAULT_TIMESERIES_OUTPUT",
                root / "shock-timeseries.csv",
            ), patch(
                "experiments.run_all.shock_recovery.DEFAULT_RUNS_OUTPUT",
                root / "shock-runs.csv",
            ), patch(
                "experiments.run_all.shock_recovery.DEFAULT_SUMMARY_OUTPUT",
                root / "shock-summary.csv",
            ), patch(
                "experiments.run_all.STATISTICAL_OUTPUT",
                root / "effects.csv",
            ), patch(
                "experiments.run_all.robustness.DEFAULT_RUNS_OUTPUT",
                root / "robustness-runs.csv",
            ), patch(
                "experiments.run_all.robustness.DEFAULT_SUMMARY_OUTPUT",
                root / "robustness-summary.csv",
            ), patch(
                "experiments.run_all.generate_all", return_value=[]
            ):
                metadata = run_all(quick=True, metadata_output=metadata_path)

            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["mode"], "quick")
            self.assertEqual(loaded["seeds"]["shock_recovery"], [1])
            self.assertGreater(loaded["row_counts"]["shock_recovery_runs"], 0)
            self.assertTrue((root / "effects.csv").exists())


if __name__ == "__main__":
    unittest.main()
