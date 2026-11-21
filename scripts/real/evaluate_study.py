#!/usr/bin/env python3
"""Score one registered SO-101 evaluation cell using the guarded real runner.

Each trial requires manual scene setup and operator scoring. Evaluation runs by
default; use --dry-run to inspect the plan without accessing hardware.
"""
from __future__ import annotations

import argparse
import json
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.real.deploy_policy import metadata
from scripts.real.evaluate_policy import read_outcome
from scripts.real.runtime import RealPolicyRunner, local_path
from scripts.real.study_protocol import (
    EVAL_CELLS, MODEL_CONDITIONS, TRAINING_SEEDS, SCORED_EPISODES,
    TOTAL_SCORED_EPISODES, WARMUP_EPISODES, evaluation_plan,
)
from scripts.eval.act_rollout import JsonlRecorder


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='configs/real/so101.yaml')
    p.add_argument('--condition', choices=MODEL_CONDITIONS, required=True,
                   help='baseline uses original demonstrations; improved uses the merged four-condition dataset')
    p.add_argument('--cell', choices=EVAL_CELLS, required=True)
    p.add_argument('--seed', type=int, choices=TRAINING_SEEDS, required=True,
                   help='Seed of the trained checkpoint (not an inference RNG seed)')
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--training-manifest', type=Path, required=True, help='Matching study_manifest.json from training run')
    p.add_argument('--output', type=Path, required=True)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--execute', dest='execute', action='store_true', help='Run real evaluation (default)')
    mode.add_argument('--dry-run', dest='execute', action='store_false', help='Print evaluation plan only')
    p.set_defaults(execute=True)
    return p


def _prepare_runner_config(args):
    from scripts.real.runtime import load_config
    cfg = load_config(args.config)
    if cfg['policy']['type'] != 'smolvla' or cfg['conditioning']['mode'] != 'language':
        raise ValueError('Study evaluation requires SmolVLA with language conditioning')
    cfg['policy']['checkpoint'] = str(local_path(args.checkpoint))
    return cfg


def map_cameras_to_policy_features(cameras, rename):
    """Map local front/wrist camera handles to the feature keys used at training."""
    uses_overhead_dataset_key = 'observation.images.overhead' in rename
    aliases = {'front': 'overhead'} if uses_overhead_dataset_key else {}
    mapped = {}
    for camera_name, settings in cameras.items():
        source_name = aliases.get(camera_name, camera_name)
        raw_feature = 'observation.images.' + source_name
        new_feature = rename.get(raw_feature, raw_feature)
        if not isinstance(new_feature, str) or not new_feature.startswith('observation.images.'):
            raise ValueError(f'Invalid renamed camera feature: {new_feature}')
        target_name = new_feature.removeprefix('observation.images.')
        if not target_name or target_name in mapped:
            raise ValueError('Camera rename_map would create an empty or duplicate camera key')
        mapped[target_name] = settings
    return mapped


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    cfg = _prepare_runner_config(args)
    cells = evaluation_plan(args.cell)
    expected_scored = SCORED_EPISODES[args.cell]
    summary = {'condition': args.condition, 'eval_cell': args.cell,
               'seed': args.seed, 'checkpoint': cfg['policy']['checkpoint'],
               'training_manifest': str(local_path(args.training_manifest)),
               'scored_episodes': expected_scored,
               'total_scored_episodes_per_model': TOTAL_SCORED_EPISODES,
               'warmup_episodes': WARMUP_EPISODES,
               'output': str(local_path(args.output)), 'will_execute': args.execute}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.execute:
        return
    manifest = json.loads(local_path(args.training_manifest).read_text(encoding='utf-8'))
    if (manifest.get('condition') != args.condition or manifest.get('seed') != args.seed or
            manifest.get('steps') != 10000 or manifest.get('batch_size') != 32):
        p.error('Training manifest condition/seed/budget does not match this evaluation')
    # Align camera feature names with the rename map saved by the training run.
    rename = manifest.get('rename_map', {})
    if not isinstance(rename, dict):
        p.error('Malformed training rename_map')
    try:
        cfg['robot']['cameras'] = map_cameras_to_policy_features(cfg['robot']['cameras'], rename)
    except ValueError as exc:
        p.error(str(exc))
    cfg['policy']['dataset_root'] = str(Path(manifest['dataset_root']))
    weights = Path(cfg['policy']['checkpoint']) / 'model.safetensors'
    with weights.open('rb') as fh:
        digest = hashlib.file_digest(fh, 'sha256').hexdigest()
    if digest != manifest.get('model_sha256'):
        p.error('Checkpoint weights do not match the training manifest')
    if Path(local_path(args.output)).exists():
        p.error('Output JSONL already exists; refuse to overwrite')
    recorder = JsonlRecorder(local_path(args.output), {
        **metadata(cfg), 'training_manifest': str(local_path(args.training_manifest)),
        'model_condition': args.condition, 'training_seed': args.seed,
        'checkpoint_sha256': digest,
    })
    try:
        runner = RealPolicyRunner(cfg)
        for item in cells:
            label = ('warmup (not scored)' if item['warmup']
                     else f"scored {item['scored_episode']}/{expected_scored}")
            input(f"[{args.condition}/seed{args.seed} {args.cell}] episode {item['episode']} {label}\n"
                  f"Position={item['position_id']}, color={item['cube_color']}, lighting={item['lighting']}, "
                  f"distractors={item['distractors']}. Confirm physical scene + safe home; Enter to run: ")
            common = {'train_condition': args.condition, 'eval_cell': args.cell,
                      'seed': args.seed, 'episode': item['episode'],
                      'position_id': item['position_id'], 'cube_color': item['cube_color'],
                      'lighting': item['lighting'], 'distractors': item['distractors'],
                      'is_warmup': item['warmup']}
            try:
                motion = runner.run_episode('cube')
                if motion['reason'] == 'stop_file':
                    recorder({**common, **motion, 'completed': False})
                    break
                if item['warmup']:
                    recorder({**common, **motion, 'completed': False})
                    print('Warmup recorded without success label; excluded from scored results.')
                    continue
                outcome = read_outcome()
                recorder({**common, **motion, **outcome, 'completed': True})
            except BaseException as exc:
                recorder({**common, 'completed': False, 'reason': 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'error',
                          'error_type': type(exc).__name__})
                raise
    finally:
        recorder.close()


if __name__ == '__main__':
    main()
