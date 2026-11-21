#!/usr/bin/env python3
"""Combine the four SO-101 real demonstration groups into one LeRobot v3 dataset.

Uses LeRobot 0.5.1's dataset_tools.merge_datasets to reindex episode metadata,
parquet shards and videos. Never concatenate filesystem directories directly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.real.study_protocol import TRAIN_CONDITIONS, DEMOS_PER_CONDITION


def validate_sources(root: Path) -> list[Path]:
    folders = [root / name for name in TRAIN_CONDITIONS]
    reference_features = reference_fps = None
    for name, folder in zip(TRAIN_CONDITIONS, folders):
        info_file = folder / "meta" / "info.json"
        if not info_file.is_file():
            raise FileNotFoundError(f"Missing LeRobot metadata for {name}: {info_file}")
        info = json.loads(info_file.read_text(encoding="utf-8"))
        if info.get("total_episodes") != DEMOS_PER_CONDITION:
            raise ValueError(f"{name}: expected {DEMOS_PER_CONDITION} episodes")
        features, fps = info.get("features"), info.get("fps")
        if not isinstance(features, dict) or not features:
            raise ValueError(f"{name}: missing feature schema")
        if reference_features is None:
            reference_features, reference_fps = features, fps
        elif features != reference_features or fps != reference_fps:
            raise ValueError(f"{name}: feature schema or FPS differs from the other training groups")
    return folders


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("data/real_demonstrations"))
    parser.add_argument("--output", type=Path, default=Path("data/real_so101_improved"))
    parser.add_argument("--repo-id", default="local/so101_improved")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    folders = validate_sources(args.input_root)
    if args.output.exists():
        parser.error(f"Output exists, refusing to overwrite: {args.output}")
    print(json.dumps({"sources": [str(p) for p in folders], "output": str(args.output),
                      "repo_id": args.repo_id,
                      "expected_episodes": DEMOS_PER_CONDITION * len(TRAIN_CONDITIONS)},
                     ensure_ascii=False, indent=2))
    if args.dry_run:
        return
    try:
        from lerobot.datasets.lerobot_dataset import LeRobotDataset
        from lerobot.datasets.dataset_tools import merge_datasets
    except ImportError as exc:
        parser.error(f"LeRobot 0.5.1 with dataset merge utilities is required: {exc}")
    datasets = [
        LeRobotDataset(repo_id=f"local/so101_{name}", root=path)
        for name, path in zip(TRAIN_CONDITIONS, folders)
    ]
    merged = merge_datasets(datasets, output_repo_id=args.repo_id, output_dir=args.output)
    count = merged.meta.total_episodes
    expected = DEMOS_PER_CONDITION * len(TRAIN_CONDITIONS)
    if count != expected:
        raise RuntimeError(f"Merged dataset has {count} episodes; expected {expected}")
    print(f"Verified merged dataset: {count} episodes at {args.output}")


if __name__ == "__main__":
    main()
