import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))

from action_log import action_log_path, append_action


class ActionLogTests(unittest.TestCase):
    def test_writes_human_and_jsonl_logs_without_extra_processes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            append_action(root, stage="TEST", status="PASS", action="did useful work", command="python tool.py", duration_ms=12, detail={"x": 1})
            human = action_log_path(root)
            jsonl = root / ".ai" / "gemini-chatgpt-actions.jsonl"
            self.assertTrue(human.exists())
            self.assertIn("did useful work", human.read_text(encoding="utf-8"))
            row = json.loads(jsonl.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["stage"], "TEST")
            self.assertEqual(row["duration_ms"], 12)


if __name__ == "__main__":
    unittest.main()
