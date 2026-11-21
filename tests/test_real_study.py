"""Offline regression coverage for the baseline/improved real SmolVLA study."""
import json
import tempfile
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import unittest

from scripts.real.evaluate_study import map_cameras_to_policy_features
from scripts.real.study_protocol import (
    collection_plan, evaluation_plan, TRAIN_CONDITIONS, MODEL_CONDITIONS,
    EVAL_CELLS, TRAINING_SEEDS, SCORED_EPISODES, TOTAL_SCORED_EPISODES,
)
from scripts.real.train_study import training_command, check_dataset
from scripts.real.record_study import record_command
from scripts.real.summarize_study import summarize, read_logs


class RealStudyProtocol(unittest.TestCase):
    def test_collection_fifty_balanced_and_recovery(self):
        for c in TRAIN_CONDITIONS:
            self.assertEqual(len(collection_plan(c)), 50)
        positions = collection_plan('randomized')
        self.assertEqual([sum(r['position_id'] == f'T{i}' for r in positions)
                          for i in range(1, 11)], [5] * 10)
        self.assertEqual(sum(r['demonstrate_drop_and_regrasp'] for r in collection_plan('recovery')), 20)
        for color in ('red', 'orange', 'yellow', 'blue', 'purple'):
            self.assertEqual(sum(r['cube_color'] == color for r in collection_plan('color')), 10)
        self.assertNotIn('green', {r['cube_color'] for r in collection_plan('color')})

    def test_evaluation_budget_is_40_id_plus_15_per_ood_and_warmup(self):
        self.assertEqual(TRAINING_SEEDS, (1000,))
        self.assertEqual(SCORED_EPISODES['in_distribution'], 40)
        self.assertEqual(sum(SCORED_EPISODES.values()), 100)
        for cell in EVAL_CELLS:
            trials = evaluation_plan(cell)
            expected = SCORED_EPISODES[cell]
            self.assertEqual(len(trials), expected + 1)
            self.assertTrue(trials[0]['warmup'])
            self.assertEqual(sum(not r['warmup'] for r in trials), expected)
        positions = [r['position_id'] for r in evaluation_plan('new_positions')[1:]]
        self.assertEqual(positions, [f'E{i}' for _ in range(3) for i in range(1, 6)])
        self.assertEqual({r['cube_color'] for r in evaluation_plan('different_object')}, {'green'})

    def test_matched_training_budget_and_dataset_contract(self):
        self.assertEqual(MODEL_CONDITIONS, ('baseline', 'improved'))
        for condition in MODEL_CONDITIONS:
            cmd = training_command(condition=condition, seed=1000, repo_id='local/ds',
                                   dataset_root=Path('/tmp/ds'), base_model=Path('/tmp/base'),
                                   output=Path('/tmp/out'))
            self.assertIn('--seed=1000', cmd)
            self.assertIn('--steps=10000', cmd)
            self.assertIn('--batch_size=32', cmd)
            self.assertIn('--policy.freeze_vision_encoder=false', cmd)
            self.assertIn('--policy.train_expert_only=false', cmd)
            self.assertIn('--policy.train_state_proj=true', cmd)
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / 'meta'
            meta.mkdir()
            base = {'total_episodes': 50, 'features': {'action': {'shape': [6]},
                    'observation.state': {'shape': [6]},
                    'observation.images.overhead': {'shape': [480, 640, 3]}}}
            (meta / 'info.json').write_text(json.dumps(base))
            with self.assertRaises(ValueError):
                check_dataset(Path(tmp), condition='improved')
            base['total_episodes'] = 200
            (meta / 'info.json').write_text(json.dumps(base))
            self.assertEqual(check_dataset(Path(tmp), condition='improved')['total_episodes'], 200)
            base['total_episodes'] = 12
            (meta / 'info.json').write_text(json.dumps(base))
            self.assertEqual(check_dataset(Path(tmp), condition='baseline')['total_episodes'], 12)
            with self.assertRaises(ValueError):
                check_dataset(Path(tmp), condition='improved')
            base['total_episodes'] = 0
            (meta / 'info.json').write_text(json.dumps(base))
            with self.assertRaises(ValueError):
                check_dataset(Path(tmp), condition='baseline')

    def test_record_command_does_not_push_to_hub(self):
        cmd = record_command(repo_id='local/study_clean', dataset_root=Path('/tmp/clean'),
                             follower_port='/dev/ttyACM0', leader_port='/dev/ttyACM1',
                             follower_id='follower', leader_id='leader', front_idx=0, wrist_idx=1)
        self.assertIn('--dataset.num_episodes=50', cmd)
        self.assertIn('--dataset.push_to_hub=false', cmd)
        with self.assertRaises(ValueError):
            record_command(repo_id='x', dataset_root=Path('/tmp/clean'),
                           follower_port='x', leader_port='y', follower_id='a', leader_id='b',
                           front_idx=1, wrist_idx=1)

    def test_summary_rejects_duplicates_and_uses_real_denominators(self):
        cases = [dict(train_condition='improved', seed=1000, eval_cell='in_distribution',
                      episode=1, success=True, completed=True, started=True, reached=True,
                      dropped=False),
                 dict(train_condition='improved', seed=1000, eval_cell='in_distribution',
                      episode=2, success=False, completed=True, started=False,
                      reached=False, dropped=True, regrasped=False)]
        totals = summarize(cases)
        self.assertEqual(len(totals), 2)  # per cell + all_cells
        self.assertEqual(totals[0]['success_rate_pct'], 50.0)
        self.assertEqual(totals[0]['no_motion_pct'], 50.0)
        self.assertEqual(totals[0]['regrasp_per_drop_pct'], 0.0)
        self.assertIsNone(totals[0]['grasp_pct'])
        with self.assertRaises(ValueError):
            summarize(cases + [cases[0]])
        with self.assertRaises(ValueError):
            summarize(cases, strict=True)

    def test_strict_summary_accepts_exact_two_model_100_rollout_protocol(self):
        cases = []
        for condition in MODEL_CONDITIONS:
            for cell, count in SCORED_EPISODES.items():
                for episode in range(1, count + 1):
                    cases.append({
                        'train_condition': condition, 'seed': 1000, 'eval_cell': cell,
                        'episode': episode, 'success': episode % 2 == 0, 'completed': True,
                    })
        result = summarize(cases, strict=True)
        self.assertEqual(len(result), len(MODEL_CONDITIONS) * (len(EVAL_CELLS) + 1))
        totals = [row for row in result if row['eval_cell'] == 'all_cells']
        self.assertEqual(len(totals), 2)
        self.assertTrue(all(row['episodes'] == TOTAL_SCORED_EPISODES == 100 for row in totals))
        id_rows = [row for row in result if row['eval_cell'] == 'in_distribution']
        self.assertTrue(all(row['episodes'] == 40 for row in id_rows))
        ood_rows = [row for row in result if row['eval_cell'] in EVAL_CELLS[1:]]
        self.assertTrue(all(row['episodes'] == 15 for row in ood_rows))

    def test_reference_dataset_camera_keys_map_to_real_robot_camera_handles(self):
        cameras = {'front': {'index_or_path': 0}, 'wrist': {'index_or_path': 1}}
        reference_map = {
            'observation.images.overhead': 'observation.images.camera1',
            'observation.images.wrist': 'observation.images.camera2',
        }
        mapped = map_cameras_to_policy_features(cameras, reference_map)
        self.assertEqual(set(mapped), {'camera1', 'camera2'})
        self.assertEqual(mapped['camera1']['index_or_path'], 0)
        self.assertEqual(mapped['camera2']['index_or_path'], 1)

    def test_local_front_camera_mapping_remains_supported(self):
        cameras = {'front': {'index_or_path': 0}, 'wrist': {'index_or_path': 1}}
        local_map = {
            'observation.images.front': 'observation.images.camera1',
            'observation.images.wrist': 'observation.images.camera2',
        }
        mapped = map_cameras_to_policy_features(cameras, local_map)
        self.assertEqual(set(mapped), {'camera1', 'camera2'})

    def test_warmup_and_incomplete_are_not_scored(self):
        cases = [{'train_condition': 'improved', 'seed': 1000, 'eval_cell': 'in_distribution',
                  'episode': 0, 'completed': False, 'is_warmup': True},
                 {'train_condition': 'improved', 'seed': 1000, 'eval_cell': 'in_distribution',
                  'episode': 1, 'completed': True, 'success': True}]
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'run.jsonl'
            p.write_text('\n'.join(json.dumps(r) for r in cases) + '\n')
            got = read_logs([p])
            self.assertEqual(len(got), 1)
            self.assertEqual(summarize(got)[0]['success_rate_pct'], 100.)


    def test_entrypoint_explicit_dry_run_never_starts_external_process(self):
        from scripts.real.record_study import main as record_main
        from scripts.real.train_study import main as train_main
        from scripts.real.evaluate_study import main as evaluate_main, build_parser

        record_args = ['--condition', 'clean', '--repo-id', 'local/study_clean',
                       '--dataset-root', '/nonexistent/study_clean',
                       '--follower-port', '/dev/ttyACM0', '--leader-port', '/dev/ttyACM1',
                       '--front-idx', '0', '--wrist-idx', '1']
        train_args = ['--condition', 'improved', '--seed', '1000',
                      '--dataset-root', '/nonexistent/study_clean',
                      '--repo-id', 'local/study_clean',
                      '--base-model', '/nonexistent/smolvla_base',
                      '--output', '/nonexistent/study_train']
        eval_args = ['--condition', 'improved', '--seed', '1000', '--cell', 'new_positions',
                     '--checkpoint', '/nonexistent/pretrained_model',
                     '--training-manifest', '/nonexistent/study_manifest.json',
                     '--output', '/nonexistent/results.jsonl']
        self.assertTrue(build_parser().parse_args(eval_args).execute)
        self.assertFalse(build_parser().parse_args(eval_args + ['--dry-run']).execute)

        with patch('subprocess.run', side_effect=AssertionError('external process launched')), \
             patch('builtins.input', side_effect=AssertionError('prompted for real robot')), \
             redirect_stdout(StringIO()):
            record_main(record_args + ['--dry-run'])
            train_main(train_args + ['--dry-run'])
            evaluate_main(eval_args + ['--dry-run'])

        # Without --dry-run, the entrypoints enter execution checks;
        # they must still refuse missing resources or request human confirmation.
        with tempfile.TemporaryDirectory() as tmp, \
             patch('builtins.input', side_effect=RuntimeError('operator confirmation reached')), \
             redirect_stdout(StringIO()):
            args = list(record_args)
            args[args.index('/nonexistent/study_clean')] = str(Path(tmp) / 'new_dataset')
            with self.assertRaisesRegex(RuntimeError, 'operator confirmation reached'):
                record_main(args)
        with redirect_stdout(StringIO()), self.assertRaises(SystemExit):
            train_main(train_args)
        with redirect_stdout(StringIO()), self.assertRaises(FileNotFoundError):
            evaluate_main(eval_args)


if __name__ == '__main__':
    unittest.main()
