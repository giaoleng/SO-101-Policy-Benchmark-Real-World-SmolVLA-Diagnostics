import json
import tempfile
import unittest
from pathlib import Path

from scripts.real.summarize_recovery import read_recovery_log, summarize_recovery


def recovery_rows():
    rows = []
    for episode in range(10):
        attempted = episode < 6
        regrasped = episode < 4
        placed = episode < 3
        rows.append({
            'episode': episode,
            'completed': True,
            'eval_cell': 'recovery',
            'dropped': True,
            'regrasp_attempted': attempted,
            'regrasped': regrasped,
            'placed': placed,
            'success': regrasped and placed,
        })
    return rows


class RecoverySummaryTests(unittest.TestCase):
    def write_log(self, root: Path, name: str, rows):
        path = root / name
        path.write_text('\n'.join(json.dumps(row) for row in rows) + '\n', encoding='utf-8')
        return path

    def test_ten_trial_recovery_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_log(Path(tmp), 'baseline.jsonl', recovery_rows())
            rows = read_recovery_log(path, 'baseline')
            summary = summarize_recovery(rows, 'baseline')
        self.assertEqual(summary['valid_drops'], 10)
        self.assertEqual(summary['regrasp_attempts'], 6)
        self.assertEqual(summary['successful_regrasps'], 4)
        self.assertEqual(summary['final_placements'], 3)
        self.assertEqual(summary['recovery_successes'], 3)
        self.assertEqual(summary['regrasp_success_per_drop_pct'], 40.0)
        self.assertEqual(summary['regrasp_success_per_attempt_pct'], 66.67)
        self.assertEqual(summary['recovery_success_per_drop_pct'], 30.0)

    def test_partial_logs_require_explicit_non_strict_mode(self):
        rows = recovery_rows()[:-1]
        with self.assertRaisesRegex(ValueError, 'expected exactly 10'):
            summarize_recovery(rows, 'baseline')
        self.assertEqual(summarize_recovery(rows, 'baseline', strict=False)['valid_drops'], 9)

    def test_invalid_recovery_success_definition_is_rejected(self):
        rows = recovery_rows()
        rows[0]['success'] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_log(Path(tmp), 'bad.jsonl', rows)
            with self.assertRaisesRegex(ValueError, 'recovery success'):
                read_recovery_log(path, 'baseline')

    def test_recovery_trial_must_contain_a_drop(self):
        rows = recovery_rows()
        rows[0]['dropped'] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_log(Path(tmp), 'bad.jsonl', rows)
            with self.assertRaisesRegex(ValueError, 'controlled drop'):
                read_recovery_log(path, 'baseline')


if __name__ == '__main__':
    unittest.main()
