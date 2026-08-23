import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "parse_review.py"
FIXTURES = ROOT / "tests" / "fixtures"
GOOD_SHA = "0123456789abcdef0123456789abcdef01234567"


class ParseReviewV1Tests(unittest.TestCase):
    def run_cli(self, fixture, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(FIXTURES / fixture), *extra],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def test_approved_contract_parses(self):
        proc = self.run_cli("review-approved.txt", "--expect-head", GOOD_SHA)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["verdict"], "APPROVED_TO_MERGE")
        self.assertEqual(payload["target_head_sha"], GOOD_SHA)

    def test_request_changes_extracts_blockers(self):
        proc = self.run_cli("review-request-changes.txt")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["verdict"], "REQUEST_CHANGES")
        self.assertEqual([x["id"] for x in payload["blocking_findings"]], ["B001", "B002"])

    def test_malformed_output_fails_closed(self):
        proc = self.run_cli("review-malformed.txt")
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["verdict"], "NEEDS_HUMAN_DECISION")

    def test_unknown_verdict_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "unknown.txt"
            p.write_text(
                f"TARGET_HEAD_SHA: {GOOD_SHA}\nVERDICT: LGTM\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), str(p)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(proc.returncode, 2)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["verdict"], "NEEDS_HUMAN_DECISION")

    def test_expected_sha_mismatch_is_rejected(self):
        proc = self.run_cli("review-wrong-sha.txt", "--expect-head", GOOD_SHA)
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"], "HEAD SHA mismatch")

    def test_abbreviated_sha_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "short.txt"
            p.write_text("TARGET_HEAD_SHA: 0123456\nVERDICT: APPROVED_TO_MERGE\n", encoding="utf-8")
            proc = subprocess.run([sys.executable, str(SCRIPT), str(p)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 2)
            payload = json.loads(proc.stdout)
            self.assertFalse(payload["ok"])
            self.assertIn("exactly 40", payload["error"])

    def test_abbreviated_expected_sha_is_rejected(self):
        proc = self.run_cli("review-approved.txt", "--expect-head", GOOD_SHA[:8])
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["ok"])
        self.assertIn("Expected HEAD SHA", payload["error"])

    def test_markdown_bold_and_backticks_formatting_parses(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "markdown.txt"
            p.write_text(
                f"**TARGET_HEAD_SHA:** `{GOOD_SHA}`\n**VERDICT:** **APPROVED_TO_MERGE**\n\nNON_BLOCKING_FINDINGS:\n- [N001] Consider adding logging\n",
                encoding="utf-8",
            )
            proc = subprocess.run([sys.executable, str(SCRIPT), str(p), "--expect-head", GOOD_SHA], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["verdict"], "APPROVED_TO_MERGE")
            self.assertEqual(payload["target_head_sha"], GOOD_SHA)
            self.assertEqual(len(payload["non_blocking_findings"]), 1)
            self.assertEqual(payload["non_blocking_findings"][0]["id"], "N001")


if __name__ == "__main__":
    unittest.main()
