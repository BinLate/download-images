import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from task_store import TaskStoreError, create_task, get_active_task_id, load_task, save_task, transition_task

NOW = datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)


class TaskStoreTests(unittest.TestCase):
    def test_create_task_writes_authoritative_state_and_active_pointer(self):
        with tempfile.TemporaryDirectory() as td:
            state = create_task(td, 'Fix a bug', 'Fix login bug', now=NOW)
            task_id = state['identity']['id']
            self.assertRegex(task_id, r'^T-20260819-001-fix-login-bug$')
            self.assertEqual(get_active_task_id(td), task_id)
            loaded = load_task(td)
            self.assertEqual(loaded['lifecycle']['current_state'], 'RECEIVED')
            self.assertEqual(loaded['classification']['complexity_tier'], 'UNCLASSIFIED')

    def test_task_id_sequence_is_stable_within_day(self):
        with tempfile.TemporaryDirectory() as td:
            first = create_task(td, 'A', 'First task', now=NOW)
            second = create_task(td, 'B', 'Second task', now=NOW)
            self.assertIn('-001-', first['identity']['id'])
            self.assertIn('-002-', second['identity']['id'])

    def test_transition_creates_checkpoint_and_append_only_history(self):
        with tempfile.TemporaryDirectory() as td:
            state = create_task(td, 'A', 'Task', now=NOW)
            state['classification'].update({'kind': 'MAINTENANCE', 'complexity_tier': 'SIMPLE', 'risk_level': 'LOW'})
            save_task(td, state, timestamp=NOW.isoformat())
            classified = transition_task(td, 'CLASSIFIED', 'classified', timestamp=NOW.isoformat())
            cp = Path(td) / classified['checkpoint']['latest_path']
            self.assertTrue(cp.exists())
            history = Path(td) / '.ai' / 'tasks' / state['identity']['id'] / 'transition-history.jsonl'
            rows = [json.loads(line) for line in history.read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[-1]['from'], 'RECEIVED')
            self.assertEqual(rows[-1]['to'], 'CLASSIFIED')

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            state = create_task(td, 'A', 'Task', now=NOW)
            p = Path(td) / '.ai' / 'tasks' / state['identity']['id'] / 'state.json'
            p.write_text('{broken', encoding='utf-8')
            with self.assertRaises(TaskStoreError) as cm:
                load_task(td)
            self.assertIn('refusing unsafe reset', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
