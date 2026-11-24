#!/usr/bin/env python3
"""Download the four SO-101 demonstration subsets from a user-selected dataset repository.

The repository ID is supplied at runtime so private dataset locations are not hard-coded
into the public source tree. Downloaded data remain local and are never uploaded by this script.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

DATASET_DIRS = {
    "clean": "cube-pickup-clean",
    "randomized": "cube-pickup-randomized",
    "recovery": "cube-pickup-recovery",
    "color": "cube-pickup-color",
}
EXPECTED_EPISODES = 50
EXPECTED_FPS = 30
REQUIRED_FEATURES = (
    "action",
    "observation.state",
    "observation.images.overhead",
    "observation.images.wrist",
)


def validate_dataset_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("total_episodes") != EXPECTED_EPISODES:
        raise ValueError(
            f"Expected {EXPECTED_EPISODES} episodes, got {metadata.get('total_episodes')}"
        )
    if metadata.get("fps") != EXPECTED_FPS:
        raise ValueError(f"Expected {EXPECTED_FPS} FPS, got {metadata.get('fps')}")
    features = metadata.get("features", {})
    missing = [key for key in REQUIRED_FEATURES if key not in features]
    if missing:
        raise ValueError(f"Missing required LeRobot features: {missing}")
    for key in ("action", "observation.state"):
        if features[key].get("shape") != [6]:
            raise ValueError(f"{key} must have shape [6]")


def _card_license(info: Any) -> str | None:
    card = getattr(info, "card_data", None)
    if card is None:
        return None
    if isinstance(card, dict):
        return card.get("license")
    return getattr(card, "license", None)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True,
                        help="Dataset repository ID; use a private repository for private demonstrations")
    parser.add_argument("--revision", default="main",
                        help="Dataset revision to resolve; the resolved commit SHA is recorded")
    parser.add_argument(
        "--condition",
        nargs="+",
        choices=tuple(DATASET_DIRS),
        default=list(DATASET_DIRS),
        help="Conditions to download; defaults to all four subsets.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/real_demonstrations"),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing local condition folders. Without this flag, existing data is preserved.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the subset download plan without downloading files.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    plan = [
        {
            "condition": condition,
            "repo_id": args.repo_id,
            "source_dir": DATASET_DIRS[condition],
            "target": str(args.output_root / condition),
        }
        for condition in args.condition
    ]
    if args.dry_run:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as exc:
        raise SystemExit(
            "huggingface_hub is required. Install it with: "
            "python -m pip install -U huggingface_hub"
        ) from exc

    api = HfApi(token=True)
    repo_info = api.dataset_info(
        repo_id=args.repo_id,
        revision=args.revision,
        files_metadata=True,
        token=True,
    )
    revision = repo_info.sha
    if not revision:
        raise RuntimeError(f"Could not resolve an immutable revision for {args.repo_id}")

    staging = args.output_root / ".hub_snapshot"
    args.output_root.mkdir(parents=True, exist_ok=True)
    allow_patterns = [f"{DATASET_DIRS[c]}/**" for c in args.condition]
    print(f"Resolving {args.repo_id} at {revision} ...")
    snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=revision,
        local_dir=str(staging),
        allow_patterns=allow_patterns,
        token=True,
    )

    siblings = getattr(repo_info, "siblings", None) or []
    completed = {}
    for item in plan:
        condition = item["condition"]
        source = staging / item["source_dir"]
        target = Path(item["target"])
        info_path = source / "meta" / "info.json"
        if not info_path.is_file():
            raise FileNotFoundError(
                f"Dataset subset '{item['source_dir']}' is missing {info_path}"
            )
        metadata = json.loads(info_path.read_text(encoding="utf-8"))
        validate_dataset_metadata(metadata)

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not args.overwrite:
                raise FileExistsError(
                    f"{target} already exists; remove it manually or pass --overwrite to replace it."
                )
            shutil.rmtree(target)
        shutil.copytree(source, target)

        prefix = item["source_dir"] + "/"
        total_bytes = sum(
            getattr(sibling, "size", 0) or 0
            for sibling in siblings
            if getattr(sibling, "rfilename", "").startswith(prefix)
        )
        completed[condition] = {
            "repo_id": args.repo_id,
            "source_dir": item["source_dir"],
            "revision": revision,
            "local_path": str(target),
            "license": _card_license(repo_info),
            "total_episodes": metadata["total_episodes"],
            "total_frames": metadata.get("total_frames"),
            "fps": metadata["fps"],
            "features": list(metadata["features"]),
            "reported_file_bytes": total_bytes or None,
        }
        print(
            f"[{condition}] Verified {metadata['total_episodes']} episodes, "
            f"{metadata.get('total_frames')} frames, {metadata['fps']} FPS."
        )

    manifest_path = args.output_root / "download_manifest.json"
    temporary_path = manifest_path.with_suffix(".json.tmp")
    temporary_path.write_text(
        json.dumps(
            {"source_repo_id": args.repo_id, "revision": revision, "conditions": completed},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(manifest_path)
    shutil.rmtree(staging, ignore_errors=True)
    print(f"Download manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
