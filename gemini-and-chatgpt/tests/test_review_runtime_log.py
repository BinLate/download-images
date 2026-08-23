import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import review_runtime_log as rrl


class ReviewRuntimeLogTests(unittest.TestCase):
    def test_start_and_append_event(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log = root / "review-runtime.jsonl"
            state = root / "review-runtime-state.json"
            rrl.start_session(log, state, target_head_sha="a" * 40, pr_url="https://github.com/x/y/pull/1", now=1000.0)
            rrl.log_event(log, state, event="PHASE_START", phase="TARGET_BEFORE", attempt=1, now=1010.0)
            rrl.log_event(log, state, event="TARGET_RESULT", phase="TARGET_BEFORE", attempt=1, status="PASS", details={"ok": True}, now=1011.0)
            rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["event"] for row in rows], ["SESSION_START", "PHASE_START", "TARGET_RESULT"])
            current = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(current["current_phase"], "TARGET_BEFORE")

    def test_phase_timeout_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); log = root / "l.jsonl"; state = root / "s.json"
            rrl.start_session(log, state, gate_timeout_sec=900, phase_timeout_sec=30, max_attempts=3, now=1000.0)
            rrl.log_event(log, state, event="PHASE_START", phase="COMPOSER_READBACK", attempt=1, now=1010.0)
            ok, result = rrl.check_limits(log, state, phase="COMPOSER_READBACK", attempt=1, now=1041.0)
            self.assertFalse(ok)
            self.assertIn("exceeds 30s", result["reason"])
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["status"], "BLOCKED")

    def test_overall_timeout_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); log = root / "l.jsonl"; state = root / "s.json"
            rrl.start_session(log, state, gate_timeout_sec=60, phase_timeout_sec=60, max_attempts=3, now=1000.0)
            rrl.log_event(log, state, event="PHASE_START", phase="WAIT_RESPONSE", attempt=1, now=1040.0)
            ok, result = rrl.check_limits(log, state, phase="WAIT_RESPONSE", attempt=1, now=1061.0)
            self.assertFalse(ok)
            self.assertIn("overall Gate E", result["reason"])

    def test_attempt_limit_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); log = root / "l.jsonl"; state = root / "s.json"
            rrl.start_session(log, state, max_attempts=3, now=1000.0)
            ok, result = rrl.check_limits(log, state, phase="INSERT", attempt=4, now=1001.0)
            self.assertFalse(ok)
            self.assertIn("max_attempts 3", result["reason"])

    def test_summary_returns_tail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); log = root / "l.jsonl"; state = root / "s.json"
            rrl.start_session(log, state, now=1000.0)
            rrl.log_event(log, state, event="PHASE_START", phase="A", attempt=1, now=1001.0)
            rrl.log_event(log, state, event="RESULT", phase="A", attempt=1, status="PASS", now=1002.0)
            payload = rrl.summarize(log, state, tail=2)
            self.assertEqual(payload["event_count_returned"], 2)
            self.assertEqual(payload["events"][0]["event"], "PHASE_START")

    def test_finish_records_status(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); log = root / "l.jsonl"; state = root / "s.json"
            rrl.start_session(log, state, now=1000.0)
            rrl.log_event(log, state, event="SESSION_FINISH", status="PASS", message="done", now=1005.0)
            current = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(current["status"], "PASS")
            self.assertEqual(current["finished_epoch"], 1005.0)


if __name__ == "__main__":
    unittest.main()
