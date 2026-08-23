import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from migrate_state import migrate_legacy_state
from task_store import get_active_task_id

SHA = '0123456789abcdef0123456789abcdef01234567'


class MigrateStateTests(unittest.TestCase):
    def test_reviewing_legacy_state_is_blocked_until_github_reconciliation(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = Path(td) / '.ai' / 'review-state.json'
            legacy.parent.mkdir(parents=True)
            legacy.write_text(json.dumps({
                'task_id': 'T-OLD',
                'state': 'REVIEWING',
                'review_round': 2,
                'max_review_rounds': 5,
                'review': 'REQUEST_CHANGES',
                'ci': 'PASS',
                'repository': 'owner/repo',
                'pr_number': 7,
                'pr_url': 'https://github.com/owner/repo/pull/7',
                'pr_state': 'OPEN',
                'head_branch': 'feat/x',
                'base_branch': 'main',
                'head_sha': SHA,
            }), encoding='utf-8')
            state = migrate_legacy_state(td, legacy, timestamp='2026-08-19T07:00:00+00:00')
            self.assertEqual(state['lifecycle']['current_state'], 'BLOCKED')
            self.assertEqual(state['lifecycle']['resume_state'], 'REVIEWING')
            self.assertEqual(state['delivery']['pr_number'], 7)
            self.assertEqual(state['delivery']['head_sha'], SHA)
            self.assertEqual(state['review']['round'], 2)
            self.assertEqual(state['review']['current_verdict'], 'REQUEST_CHANGES')
            self.assertFalse(state['review']['approval_valid'])
            self.assertEqual(state['verification']['overall_status'], 'PARTIAL')
            self.assertEqual(get_active_task_id(td), state['identity']['id'])
            self.assertTrue(any(x.get('type') == 'GITHUB_IDENTITY_RECONCILIATION_REQUIRED' for x in state['blockers']))

    def test_legacy_approved_state_cannot_migrate_as_authoritative_approval(self):
        with tempfile.TemporaryDirectory() as td:
            legacy = Path(td) / 'review-state.json'
            legacy.write_text(json.dumps({
                'task_id': 'T-OLD',
                'state': 'APPROVED',
                'review_round': 1,
                'max_review_rounds': 5,
                'review': 'APPROVED_TO_MERGE',
                'head_sha': SHA,
            }), encoding='utf-8')
            state = migrate_legacy_state(td, legacy, timestamp='2026-08-19T07:00:00+00:00')
            self.assertEqual(state['lifecycle']['current_state'], 'HUMAN_DECISION')
            self.assertFalse(state['review']['approval_valid'])
            self.assertIsNone(state['release']['approved_sha'])
            self.assertTrue(state['release']['human_required'])


if __name__ == '__main__':
    unittest.main()
