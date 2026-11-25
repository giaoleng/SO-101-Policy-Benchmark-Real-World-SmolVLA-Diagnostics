import unittest

from scripts.real.download_study_datasets import (
    DATASET_DIRS,
    REQUIRED_FEATURES,
    build_parser,
    validate_dataset_metadata,
)


class StudyDatasetDownloadTests(unittest.TestCase):
    def test_dataset_repository_is_supplied_at_runtime(self):
        args = build_parser().parse_args(["--repo-id", "owner/private-so101", "--dry-run"])
        self.assertEqual(args.repo_id, "owner/private-so101")
        self.assertEqual(args.revision, "main")
        self.assertEqual(
            DATASET_DIRS,
            {
                "clean": "cube-pickup-clean",
                "randomized": "cube-pickup-randomized",
                "recovery": "cube-pickup-recovery",
                "color": "cube-pickup-color",
            },
        )

    def test_repo_id_is_required(self):
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["--dry-run"])

    def test_expected_lerobot_schema_is_validated(self):
        metadata = {
            "total_episodes": 50,
            "fps": 30,
            "features": {
                "action": {"shape": [6]},
                "observation.state": {"shape": [6]},
                "observation.images.front": {"shape": [480, 640, 3]},
                "observation.images.wrist": {"shape": [480, 640, 3]},
            },
        }
        validate_dataset_metadata(metadata)
        self.assertEqual(len(REQUIRED_FEATURES), 4)
        self.assertIn('observation.images.front', REQUIRED_FEATURES)
        features = metadata['features']
        features['observation.images.overhead'] = features.pop('observation.images.front')
        validate_dataset_metadata(metadata)  # older data remain readable
        features.pop('observation.images.overhead')
        with self.assertRaises(ValueError):
            validate_dataset_metadata(metadata)

    def test_wrong_episode_count_is_rejected(self):
        metadata = {
            "total_episodes": 49,
            "fps": 30,
            "features": {
                "action": {"shape": [6]},
                "observation.state": {"shape": [6]},
                "observation.images.front": {"shape": [480, 640, 3]},
                "observation.images.wrist": {"shape": [480, 640, 3]},
            },
        }
        with self.assertRaises(ValueError):
            validate_dataset_metadata(metadata)


if __name__ == "__main__":
    unittest.main()
