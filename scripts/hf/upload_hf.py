#!/usr/bin/env python3
"""Upload a local folder only to a private Hugging Face Hub repository.

Public destinations are rejected to prevent accidental publication of private
robot demonstrations, videos, checkpoints, or evaluation logs.
"""
import argparse
import os
from pathlib import Path

from huggingface_hub import HfApi, create_repo, login, upload_folder
from huggingface_hub.errors import RepositoryNotFoundError


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Upload a local folder to a private Hugging Face Hub repository.")
    p.add_argument("--folder", required=True, help="Local folder to upload.")
    p.add_argument("--repo-id", required=True, help='Private target Hub repo id like "username/private_repo".')
    p.add_argument("--repo-type", default="dataset", choices=["dataset", "model", "space"])
    p.add_argument("--message", default="Upload private project artifact", help="Commit message.")
    p.add_argument("--create-if-missing", action="store_true",
                   help="Create the target repository as private if it does not exist.")
    p.add_argument("--token", default=os.environ.get("HF_TOKEN"),
                   help="Hugging Face token (defaults to HF_TOKEN env var or local login).")
    return p.parse_args()


def ensure_private_repo(repo_id: str, repo_type: str, *, create_if_missing: bool, token=None):
    api = HfApi(token=token) if token else HfApi()
    try:
        info = api.repo_info(repo_id=repo_id, repo_type=repo_type, token=token)
    except RepositoryNotFoundError:
        if not create_if_missing:
            raise
        create_repo(repo_id=repo_id, repo_type=repo_type, private=True, exist_ok=True, token=token)
        info = api.repo_info(repo_id=repo_id, repo_type=repo_type, token=token)
    if getattr(info, "private", False) is not True:
        raise ValueError(
            f"Refusing upload to public Hub repository {repo_type}:{repo_id}; "
            "use a private repository for project data and model artifacts."
        )
    return info


def main() -> None:
    args = parse_args()
    folder_path = Path(args.folder).expanduser().resolve()
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")
    if args.token:
        login(token=args.token)
    ensure_private_repo(args.repo_id, args.repo_type,
                        create_if_missing=args.create_if_missing, token=args.token)
    upload_folder(
        folder_path=str(folder_path),
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        commit_message=args.message,
        token=args.token,
    )
    print(f"[upload_hf] Uploaded to private {args.repo_type}:{args.repo_id}")


if __name__ == "__main__":
    main()
