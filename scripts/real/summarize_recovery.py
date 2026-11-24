#!/usr/bin/env python3
"""Summarize the separate ten-trial controlled-drop recovery evaluation."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

RECOVERY_TESTS_PER_MODEL = 10
MODEL_NAMES = ('baseline', 'improved')
REQUIRED_FLAGS = ('dropped', 'regrasp_attempted', 'regrasped', 'placed', 'success')


def read_recovery_log(path: Path, expected_model: str) -> list[dict]:
    if expected_model not in MODEL_NAMES:
        raise ValueError(f'Unknown model condition: {expected_model}')
    rows, seen = [], set()
    with path.open(encoding='utf-8') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path}:{line_number}: invalid JSON') from exc
            if not isinstance(row, dict):
                raise ValueError(f'{path}:{line_number}: expected JSON object')
            if type(row.get('completed')) is not bool:
                raise ValueError(f'{path}:{line_number}: completed must be boolean')
            if row.get('is_warmup') is True or not row['completed']:
                continue
            recorded_model = row.get('train_condition', row.get('model_condition'))
            if recorded_model is not None and recorded_model != expected_model:
                raise ValueError(
                    f'{path}:{line_number}: log says {recorded_model}, expected {expected_model}'
                )
            eval_cell = row.get('eval_cell')
            if eval_cell is not None and eval_cell != 'recovery':
                raise ValueError(f'{path}:{line_number}: expected eval_cell=recovery')
            episode = row.get('episode')
            if type(episode) is not int or episode in seen:
                raise ValueError(f'{path}:{line_number}: episode must be a unique integer')
            seen.add(episode)
            missing = [key for key in REQUIRED_FLAGS if type(row.get(key)) is not bool]
            if missing:
                raise ValueError(f'{path}:{line_number}: missing boolean recovery labels {missing}')
            if row['dropped'] is not True:
                raise ValueError(f'{path}:{line_number}: a scored recovery trial must contain a controlled drop')
            if row['regrasped'] and not row['regrasp_attempted']:
                raise ValueError(f'{path}:{line_number}: regrasped requires regrasp_attempted')
            if row['success'] != (row['regrasped'] and row['placed']):
                raise ValueError(
                    f'{path}:{line_number}: recovery success must mean re-grasp followed by final placement'
                )
            rows.append(row)
    return rows


def summarize_recovery(rows: list[dict], model: str, *, strict: bool = True) -> dict:
    if model not in MODEL_NAMES:
        raise ValueError(f'Unknown model condition: {model}')
    if not rows:
        raise ValueError(f'No completed controlled-drop trials for {model}')
    if len(rows) > RECOVERY_TESTS_PER_MODEL or (strict and len(rows) != RECOVERY_TESTS_PER_MODEL):
        raise ValueError(
            f'{model}: expected exactly {RECOVERY_TESTS_PER_MODEL} valid drops, got {len(rows)}'
        )
    attempts = sum(row['regrasp_attempted'] for row in rows)
    regrasped = sum(row['regrasped'] for row in rows)
    placed = sum(row['placed'] for row in rows)
    recovered = sum(row['success'] for row in rows)
    drops = len(rows)
    return {
        'model': model,
        'valid_drops': drops,
        'regrasp_attempts': attempts,
        'successful_regrasps': regrasped,
        'final_placements': placed,
        'recovery_successes': recovered,
        'regrasp_attempt_rate_pct': round(100 * attempts / drops, 2),
        'regrasp_success_per_drop_pct': round(100 * regrasped / drops, 2),
        'regrasp_success_per_attempt_pct': round(100 * regrasped / attempts, 2) if attempts else None,
        'recovery_success_per_drop_pct': round(100 * recovered / drops, 2),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path, help='Baseline recovery JSONL')
    parser.add_argument('--improved', required=True, type=Path, help='Improved recovery JSONL')
    parser.add_argument('--csv', type=Path, help='Optional local CSV output; refuses overwrite')
    parser.add_argument('--allow-partial', action='store_true',
                        help='Allow fewer than ten completed valid drops per model')
    args = parser.parse_args(argv)
    strict = not args.allow_partial
    try:
        baseline = summarize_recovery(read_recovery_log(args.baseline, 'baseline'), 'baseline', strict=strict)
        improved = summarize_recovery(read_recovery_log(args.improved, 'improved'), 'improved', strict=strict)
    except ValueError as exc:
        parser.error(str(exc))
    result = [baseline, improved]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open('x', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result[0]))
            writer.writeheader()
            writer.writerows(result)


if __name__ == '__main__':
    main()
