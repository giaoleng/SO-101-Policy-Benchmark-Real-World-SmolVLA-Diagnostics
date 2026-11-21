#!/usr/bin/env python3
"""Offline aggregate of real SmolVLA study JSONL; never invent absent rollouts.

Groups are model condition x training seed x evaluation cell. Warmup and incomplete
runs are excluded from all denominators. Output can be saved to CSV locally.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def wilson_interval(successes: int, total: int, z: float = 1.96):
    if total <= 0:
        raise ValueError('total must be positive')
    p = successes / total
    d = 1 + z*z/total
    center = (p + z*z/(2*total)) / d
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / d
    return max(0., center-half), min(1., center+half)


from scripts.real.study_protocol import (
    EVAL_CELLS, MODEL_CONDITIONS, TRAINING_SEEDS, SCORED_EPISODES,
    TOTAL_SCORED_EPISODES,
)


def read_logs(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        with path.open(encoding='utf-8') as stream:
            for n, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'{path}:{n}: invalid JSON') from exc
                if not isinstance(row, dict):
                    raise ValueError(f'{path}:{n}: expected JSON object')
                if type(row.get('completed')) is not bool:
                    raise ValueError(f'{path}:{n}: completed must be boolean')
                if row.get('is_warmup') is True or not row['completed']:
                    continue
                if (row.get('train_condition') not in MODEL_CONDITIONS or
                        row.get('eval_cell') not in EVAL_CELLS or
                        type(row.get('seed')) is not int or row['seed'] not in TRAINING_SEEDS or
                        type(row.get('success')) is not bool):
                    raise ValueError(f'{path}:{n}: requires train_condition/eval_cell/seed/success')
                for flag in ('started', 'reached', 'grasped', 'dropped', 'regrasp_attempted', 'regrasped'):
                    if flag in row and type(row[flag]) is not bool:
                        raise ValueError(f'{path}:{n}: {flag} must be boolean')
                rows.append(row)
    return rows


def metric(rows, key, *, negate=False, subset=None):
    relevant = [r for r in rows if subset is None or r.get(subset) is True]
    if not relevant or any(type(r.get(key)) is not bool for r in relevant):
        return None
    return round(100 * sum((not r[key]) if negate else r[key] for r in relevant) / len(relevant), 2)


def summarize(rows: list[dict], *, strict=False) -> list[dict]:
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        key = (row['train_condition'], row['seed'], row['eval_cell'])
        token = (*key, row.get('episode'))
        if type(row.get('episode')) is not int or token in seen:
            raise ValueError(f'Duplicate/missing scored episode: {token}')
        expected = SCORED_EPISODES[row['eval_cell']]
        if not 1 <= row['episode'] <= expected:
            raise ValueError(f'Scored episode index out of range for {key}: {row["episode"]}')
        seen.add(token)
        groups[key].append(row)
    if strict:
        expected_groups = {
            (condition, seed, cell)
            for condition in MODEL_CONDITIONS
            for seed in TRAINING_SEEDS
            for cell in EVAL_CELLS
        }
        missing = expected_groups - groups.keys()
        if missing:
            raise ValueError(f'Missing {len(missing)} model/seed/cell groups')

    def row_for(condition, seed, cell, cases):
        n = len(cases)
        if n <= 0:
            raise ValueError(f'No scored episodes for {condition}/seed{seed}/{cell}')
        wins = sum(r['success'] for r in cases)
        lo, hi = wilson_interval(wins, n)
        return {
            'condition': condition, 'seed': seed, 'eval_cell': cell,
            'episodes': n, 'successes': wins,
            'success_rate_pct': round(100 * wins / n, 2),
            'wilson95_lower_pct': round(100 * lo, 2),
            'wilson95_upper_pct': round(100 * hi, 2),
            'no_motion_pct': metric(cases, 'started', negate=True),
            'reach_pct': metric(cases, 'reached'),
            'grasp_pct': metric(cases, 'grasped'),
            'drop_pct': metric(cases, 'dropped'),
            'regrasp_per_drop_pct': metric(cases, 'regrasped', subset='dropped'),
            'recovery_per_drop_pct': metric(cases, 'success', subset='dropped'),
        }

    output = []
    by_policy = defaultdict(list)
    for (condition, seed, cell), cases in sorted(groups.items()):
        n = len(cases)
        expected = SCORED_EPISODES[cell]
        if n > expected or (strict and n != expected):
            raise ValueError(f'Invalid scored episode count for {condition}/{seed}/{cell}: {n}, expected {expected}')
        if strict and {r['episode'] for r in cases} != set(range(1, expected + 1)):
            raise ValueError(f'Incomplete scored episode indices for {condition}/{seed}/{cell}')
        output.append(row_for(condition, seed, cell, cases))
        by_policy[(condition, seed)].extend(cases)
    for (condition, seed), cases in sorted(by_policy.items()):
        if strict and len(cases) != TOTAL_SCORED_EPISODES:
            raise ValueError(f'Invalid total for {condition}/seed{seed}: {len(cases)}, expected {TOTAL_SCORED_EPISODES}')
        output.append(row_for(condition, seed, 'all_cells', cases))
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path, nargs='+')
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--strict', action='store_true',
                        help='Require baseline/improved x 1 seed x 5 cells, with 40 ID and 15 per OOD cell')
    args = parser.parse_args(argv)
    rows = read_logs(args.inputs)
    if not rows:
        parser.error('No completed scored rollouts')
    try:
        result = summarize(rows, strict=args.strict)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open('x', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=list(result[0]))
            writer.writeheader()
            writer.writerows(result)


if __name__ == '__main__':
    main()
