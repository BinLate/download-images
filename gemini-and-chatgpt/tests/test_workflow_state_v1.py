import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workflow_state.py"


class WorkflowStateV1Tests(unittest.TestCase):
    def run_cli(self, *args, check=True):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and proc.returncode != 0:
            self.fail(f"command failed: {proc.stderr}\nstdout={proc.stdout}")
        return proc

    def test_init_defaults_to_five_review_rounds(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "review-state.json"
            proc = self.run_cli("init", "--task", "T-001", "--file", str(state))
            payload = json.loads(proc.stdout)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(payload["state"], "TASK_RECEIVED")
            self.assertEqual(saved["review_round"], 0)
            self.assertEqual(saved["max_review_rounds"], 5)
            self.assertIsNone(saved["head_sha"])

    def test_show_set_and_next_round_preserve_v1_contract(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "review-state.json"
            self.run_cli("init", "--task", "T-002", "--file", str(state))
            self.run_cli("set", "--file", str(state), "--state", "IMPLEMENTING", "--ci", "PASS")
            shown = json.loads(self.run_cli("show", "--file", str(state)).stdout)
            self.assertEqual(shown["state"], "IMPLEMENTING")
            self.assertEqual(shown["ci"], "PASS")
            bumped = json.loads(self.run_cli("next-round", "--file", str(state)).stdout)
            self.assertEqual(bumped["state"], "REVIEWING")
            self.assertEqual(bumped["review_round"], 1)

    def test_review_round_limit_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "review-state.json"
            self.run_cli("init", "--task", "T-003", "--max-rounds", "1", "--file", str(state))
            self.run_cli("next-round", "--file", str(state))
            proc = self.run_cli("next-round", "--file", str(state), check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Review round limit reached", proc.stderr)


if __name__ == "__main__":
    unittest.main()
