import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from orchestrator import (
    begin_verification,
    classify_and_route,
    enter_review,
    initialize_task,
    record_review_verdict,
    run_verification,
    sync_delivery,
)
from parse_review import parse
from review_prompt import build_prompt
from task_store import load_task
from verification_gate import CheckSpec

SHA1 = "1" * 40
SHA2 = "2" * 40


class MVPInternalE2ETests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.contract = self.root / "review-contract.md"
        self.contract.write_text(
            "Return one verdict: APPROVED_TO_MERGE, REQUEST_CHANGES, or NEEDS_HUMAN_DECISION. "
            "Always include the exact TARGET_HEAD_SHA.",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _reviewing(self, sha=SHA1):
        initialize_task(self.root, "Fix typo in README", "Fix typo")
        classify_and_route(self.root)
        begin_verification(self.root, sha)
        run_verification(
            self.root,
            sha,
            [CheckSpec("focused", "FOCUSED_TEST", "python -c \"print('ok')\"", True)],
        )
        sync_delivery(
            self.root,
            head_sha=sha,
            pr_number=12,
            pr_url="https://github.com/example/repo/pull/12",
            pr_state="OPEN",
            repository="example/repo",
            base_branch="main",
            head_branch="ai/fix-typo",
        )
        return enter_review(self.root)

    def test_approved_path_reaches_human_release_gate(self):
        state = self._reviewing()
        prompt = build_prompt(self.root, contract_path=self.contract, diff_context="README typo only")
        self.assertIn(f"TARGET_HEAD_SHA: {SHA1}", prompt)
        self.assertIn("Verification evidence bound to TARGET_HEAD_SHA", prompt)
        parsed = parse(f"TARGET_HEAD_SHA: {SHA1}\nVERDICT: APPROVED_TO_MERGE\n")
        self.assertEqual(parsed["verdict"], "APPROVED_TO_MERGE")
        self.assertEqual(parsed["target_head_sha"], SHA1)
        state = record_review_verdict(self.root, parsed["verdict"], parsed["target_head_sha"])
        self.assertEqual(state["lifecycle"]["current_state"], "RELEASE_GATE")
        self.assertEqual(state["release"]["merge_policy"], "human_only")
        self.assertEqual(state["release"]["approved_sha"], SHA1)

    def test_request_changes_new_candidate_requires_fresh_round(self):
        self._reviewing()
        record_review_verdict(self.root, "REQUEST_CHANGES", SHA1, findings=[{"id": "F1"}])
        begin_verification(self.root, SHA2)
        run_verification(
            self.root,
            SHA2,
            [CheckSpec("focused2", "FOCUSED_TEST", "python -c \"print('fixed')\"", True)],
        )
        sync_delivery(
            self.root,
            head_sha=SHA2,
            pr_number=12,
            pr_url="https://github.com/example/repo/pull/12",
            pr_state="OPEN",
            repository="example/repo",
            base_branch="main",
            head_branch="ai/fix-typo",
        )
        state = enter_review(self.root)
        self.assertEqual(state["review"]["round"], 2)
        self.assertEqual(state["review"]["current_target_sha"], SHA2)
        self.assertFalse(state["review"]["approval_valid"])
        prompt = build_prompt(self.root, contract_path=self.contract)
        self.assertIn(f"TARGET_HEAD_SHA: {SHA2}", prompt)
        self.assertNotIn(f"TARGET_HEAD_SHA: {SHA1}", prompt)

    def test_wrong_sha_never_releases(self):
        self._reviewing()
        with self.assertRaises(Exception):
            record_review_verdict(self.root, "APPROVED_TO_MERGE", SHA2)
        state = load_task(self.root)
        self.assertEqual(state["lifecycle"]["current_state"], "REVIEWING")


if __name__ == "__main__":
    unittest.main()
