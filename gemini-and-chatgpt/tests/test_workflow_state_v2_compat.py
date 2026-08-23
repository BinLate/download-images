import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workflow_state.py"
sys.path.insert(0, str(ROOT / "scripts"))
from orchestrator import classify_and_route, initialize_task


class WorkflowStateV2CompatTests(unittest.TestCase):
    def test_show_projects_active_v2_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            initialize_task(root, "Fix typo in README", "Fix typo")
            classify_and_route(root)
            legacy = root / ".ai" / "review-state.json"
            proc = subprocess.run([sys.executable, str(SCRIPT), "show", "--file", str(legacy)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertTrue(data["v2_authoritative"])
            self.assertEqual(data["state"], "IMPLEMENTING")

    def test_no_active_v2_preserves_legacy_behavior(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".ai" / "review-state.json"
            proc = subprocess.run([sys.executable, str(SCRIPT), "init", "--task", "T1", "--file", str(path)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = subprocess.run([sys.executable, str(SCRIPT), "set", "--file", str(path), "--state", "PLANNING"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["state"], "PLANNING")


if __name__ == "__main__":
    unittest.main()
