import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from task_store import create_checkpoint, create_task, load_task, restore_checkpoint, save_task, transition_task

NOW = datetime(2026, 8, 19, 7, 0, tzinfo=timezone.utc)
SHA = '0123456789abcdef0123456789abcdef01234567'


class CheckpointTests(unittest.TestCase):
    def test_manual_checkpoint_and_restore_dynamic_state(self):
        with tempfile.TemporaryDirectory() as td:
            state = create_task(td, 'A', 'Task', now=NOW)
            state['classification'].update({'kind': 'MAINTENANCE', 'complexity_tier': 'SIMPLE', 'risk_level': 'LOW'})
            state['implementation']['branch'] = 'feat/demo'
            state['implementation']['candidate_sha'] = SHA
            save_task(td, state, timestamp=NOW.isoformat())
            state = transition_task(td, 'CLASSIFIED', 'classified', timestamp=NOW.isoformat())
            state = transition_task(td, 'IMPLEMENTING', 'start', timestamp=NOW.isoformat())
            cp_path, state = create_checkpoint(td, state, reason='MANUAL', resume_hint='resume implementation', timestamp=NOW.isoformat())

            mutated = load_task(td)
            mutated['implementation']['branch'] = 'broken-branch'
            save_task(td, mutated, timestamp=NOW.isoformat())

            restored = restore_checkpoint(td, cp_path, timestamp=NOW.isoformat())
            self.assertEqual(restored['implementation']['branch'], 'feat/demo')
            self.assertEqual(restored['lifecycle']['current_state'], 'IMPLEMENTING')
            self.assertEqual(restored['checkpoint']['latest_path'], cp_path.relative_to(Path(td).resolve()).as_posix())


if __name__ == '__main__':
    unittest.main()
