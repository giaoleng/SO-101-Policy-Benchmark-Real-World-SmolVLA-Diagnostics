#!/usr/bin/env python3
"""Generate and run matched-budget SmolVLA finetuning commands.

Training runs by default; use --dry-run to inspect the command. No robot is touched.
The LeRobot CLI version and feature names must be verified on the training host.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import subprocess

from scripts.real.study_protocol import (
    BASELINE_CONDITION, MODEL_CONDITIONS, TRAINING_SEEDS, DEMOS_PER_CONDITION,
    TRAIN_CONDITIONS, IMPROVED_CONDITION,
)


def training_command(*, condition: str, seed: int, repo_id: str, dataset_root: Path,
                     base_model: Path, output: Path, device='cuda', rename_map=None) -> list[str]:
    if condition not in MODEL_CONDITIONS or seed not in TRAINING_SEEDS:
        raise ValueError('condition/seed must be declared in the study protocol')
    if not repo_id or not str(base_model).strip():
        raise ValueError('repo_id and base_model are required')
    command = [
        'lerobot-train', f'--dataset.repo_id={repo_id}',
        f'--dataset.root={dataset_root}', f'--policy.path={base_model}',
        f'--policy.device={device}', '--policy.push_to_hub=false',
        '--steps=10000', '--batch_size=32', '--save_freq=2000',
        '--policy.freeze_vision_encoder=false', '--policy.train_expert_only=false',
        '--policy.train_state_proj=true',
        f'--seed={seed}', f'--output_dir={output}',
        f'--job_name=real_smolvla_{condition}_seed{seed}',
    ]
    if rename_map:
        command.append('--rename_map=' + json.dumps(rename_map, separators=(',', ':')))
    return command


def check_dataset(root: Path, condition: str = 'clean'):
    if condition not in MODEL_CONDITIONS:
        raise ValueError(f'Unknown model condition: {condition}')
    info = json.loads((root / 'meta' / 'info.json').read_text(encoding='utf-8'))
    n = info.get('total_episodes')
    if type(n) is not int or n < 1:
        raise ValueError(f'{root}: expected at least one expert demonstration, got {n}')
    if condition == IMPROVED_CONDITION and n != DEMOS_PER_CONDITION * len(TRAIN_CONDITIONS):
        raise ValueError(f'{root}: improved requires all {DEMOS_PER_CONDITION * len(TRAIN_CONDITIONS)} merged demonstrations, got {n}')
    features = info.get('features', {})
    for key in ('action', 'observation.state'):
        if features.get(key, {}).get('shape') != [6]:
            raise ValueError(f'{root}: {key} must describe six SO-101 joint values')
    if not any(key.startswith('observation.images.') for key in features):
        raise ValueError(f'{root}: missing image observations')
    return info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--condition', required=True, choices=MODEL_CONDITIONS)
    parser.add_argument('--seed', required=True, type=int, choices=TRAINING_SEEDS)
    parser.add_argument('--dataset-root', required=True, type=Path,
                        help='Baseline dataset or the 200-episode merged Improved dataset')
    parser.add_argument('--repo-id', required=True)
    parser.add_argument('--base-model', required=True, type=Path, help='Local SmolVLA base checkpoint')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--rename-map', default='{"observation.images.overhead":"observation.images.camera1","observation.images.wrist":"observation.images.camera2"}',
                        help='JSON mapping of dataset feature names to model keys; empty JSON disables')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--execute', dest='execute', action='store_true', help='Train the policy (default)')
    mode.add_argument('--dry-run', dest='execute', action='store_false', help='Print training command only')
    parser.set_defaults(execute=True)
    args = parser.parse_args(argv)
    rename = json.loads(args.rename_map)
    if not isinstance(rename, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in rename.items()):
        parser.error('--rename-map must be a JSON object with string keys/values')
    cmd = training_command(condition=args.condition, seed=args.seed, repo_id=args.repo_id,
                           dataset_root=args.dataset_root, base_model=args.base_model,
                           output=args.output, device=args.device, rename_map=rename)
    print(json.dumps({'condition': args.condition, 'seed': args.seed, 'training_command': cmd,
                      'will_execute': args.execute}, ensure_ascii=False, indent=2))
    if not args.execute:
        return
    if not args.base_model.is_dir():
        parser.error('Local pretrained checkpoint directory not found')
    if args.output.exists():
        parser.error(f'Output already exists (refuse overwrite): {args.output}')
    info = check_dataset(args.dataset_root, condition=args.condition)
    names = set(info['features'])
    if not set(rename).issubset(names):
        parser.error(f'Rename keys absent from dataset metadata: {sorted(set(rename) - names)}')
    env = dict(os.environ)
    env['HF_HUB_OFFLINE'] = '1'
    env['TRANSFORMERS_OFFLINE'] = '1'
    subprocess.run(cmd, env=env, check=True)
    checkpoint = args.output / 'checkpoints' / '010000' / 'pretrained_model'
    if not (checkpoint / 'config.json').is_file():
        raise FileNotFoundError(f'Expected final checkpoint missing: {checkpoint}')
    trained_config = json.loads((checkpoint / 'config.json').read_text(encoding='utf-8'))
    if (trained_config.get('freeze_vision_encoder') is not False or
            trained_config.get('train_expert_only') is not False or
            trained_config.get('train_state_proj') is not True):
        raise ValueError('Checkpoint configuration does not confirm full-parameter training flags')
    # Package feature schema with the same image rename map used at training.
    snapshot = dict(info)
    features = dict(info['features'])
    for old_key, new_key in rename.items():
        if old_key in features and old_key != new_key:
            if new_key in features:
                raise ValueError(f'Duplicate training image feature after rename: {new_key}')
            features[new_key] = features.pop(old_key)
    snapshot['features'] = features
    snapshot['action_semantics'] = 'so101_degrees_gripper_percent'
    schema_path = checkpoint / 'dataset_info.json'
    if not schema_path.exists():
        with schema_path.open('x', encoding='utf-8') as fh:
            json.dump(snapshot, fh, ensure_ascii=False, indent=2)
    elif json.loads(schema_path.read_text(encoding='utf-8')).get('features') != features:
        raise ValueError('Existing checkpoint dataset_info.json does not match the renamed training schema')
    with (checkpoint / 'model.safetensors').open('rb') as fh:
        model_sha256 = hashlib.file_digest(fh, 'sha256').hexdigest()
    manifest = {'condition': args.condition, 'seed': args.seed, 'dataset_repo_id': args.repo_id,
                'dataset_root': str(args.dataset_root.resolve()), 'base_model': str(args.base_model.resolve()),
                'output_dir': str(args.output.resolve()), 'checkpoint_path': str(checkpoint.resolve()), 'model_sha256': model_sha256,
                'demonstrations': info['total_episodes'], 'steps': 10000, 'batch_size': 32,
                'save_freq': 2000, 'rename_map': rename,
                'finetuning_method': 'full', 'freeze_vision_encoder': False,
                'train_expert_only': False, 'train_state_proj': True,
                'dataset_composition': ('four_conditions_merged' if args.condition == IMPROVED_CONDITION else 'original_baseline')}
    with (args.output / 'study_manifest.json').open('x', encoding='utf-8') as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
