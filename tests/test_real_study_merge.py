"""Offline source-layout checks for the Improved LeRobot merge entry."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts.real.merge_study_datasets import validate_sources
from scripts.real.study_protocol import TRAIN_CONDITIONS


class ImprovedMergeDatasetTests(unittest.TestCase):
    def test_four_compatible_datasets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in TRAIN_CONDITIONS:
                meta = root / name / "meta"
                meta.mkdir(parents=True)
                (meta / "info.json").write_text(
                    json.dumps({"total_episodes": 50, "fps": 30,
                                "features": {"action": {"shape": [6]},
                                             "observation.state": {"shape": [6]}}}),
                    encoding="utf-8",
                )
            self.assertEqual(len(validate_sources(root)), 4)
            bad = root / "color" / "meta" / "info.json"
            obj = json.loads(bad.read_text(encoding="utf-8"))
            obj["total_episodes"] = 49
            bad.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_sources(root)


if __name__ == "__main__":
    unittest.main()
