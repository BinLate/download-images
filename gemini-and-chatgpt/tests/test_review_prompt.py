import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from orchestrator import begin_verification, classify_and_route, enter_review, initialize_task, run_verification, sync_delivery
from review_prompt import ReviewPromptError, build_prompt
from task_store import load_task, save_task, task_dir
from verification_gate import CheckSpec

SHA = "c" * 40


class ReviewPromptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.contract = ROOT / "references" / "review-contract.md"

    def tearDown(self):
        self.tmp.cleanup()

    def _prepare(self):
        initialize_task(self.root, "Fix typo in README", "Fix typo")
        classify_and_route(self.root)
        state = load_task(self.root)
        state["requirements"]["acceptance_criteria"] = ["README wording is corrected", "regression test passes"]
        state["requirements"]["constraints"] = ["Do not change runtime behavior"]
        save_task(self.root, state)
        begin_verification(self.root, SHA, branch="ai/fix", changed_files=["README.md"])
        run_verification(self.root, SHA, [CheckSpec("focused", "FOCUSED_TEST", "python -c \"print('PASS-EVIDENCE')\"", True)])
        sync_delivery(self.root, head_sha=SHA, pr_number=7, pr_url="https://github.com/o/r/pull/7", pr_state="OPEN", repository="o/r", base_branch="main", head_branch="ai/fix")
        return enter_review(self.root)

    def test_prompt_contains_exact_sha_acceptance_and_qa_evidence(self):
        state = self._prepare()
        prompt = build_prompt(self.root, contract_path=self.contract, diff_context="diff --git a/README.md b/README.md")
        self.assertIn(f"TARGET_HEAD_SHA: {SHA}", prompt)
        self.assertIn("README wording is corrected", prompt)
        self.assertIn("PASS-EVIDENCE", prompt)
        self.assertIn("README.md", prompt)
        self.assertIn(state["identity"]["id"], prompt)
        self.assertIn("fresh ChatGPT Web conversation", prompt)

    def test_prompt_does_not_dump_project_context_secret_fields(self):
        self._prepare()
        ai = self.root / ".ai"; ai.mkdir(exist_ok=True)
        (ai / "project-context.json").write_text(json.dumps({"environment": {"values": {"API_TOKEN": "SUPER_SECRET_VALUE"}}}), encoding="utf-8")
        prompt = build_prompt(self.root, contract_path=self.contract)
        self.assertNotIn("SUPER_SECRET_VALUE", prompt)
        self.assertNotIn("API_TOKEN", prompt)

    def test_prompt_rejects_stale_review_target(self):
        self._prepare()
        state = load_task(self.root)
        state["review"]["current_target_sha"] = "d" * 40
        save_task(self.root, state)
        with self.assertRaises(ReviewPromptError):
            build_prompt(self.root, contract_path=self.contract)

    def test_prior_findings_are_projected_without_chat_history(self):
        state = self._prepare()
        history = task_dir(self.root, state["identity"]["id"]) / "review-history.jsonl"
        history.write_text(json.dumps({"round": 0, "target_sha": "b" * 40, "verdict": "REQUEST_CHANGES", "findings": [{"id": "B001", "text": "old bug", "disposition": "ACCEPT_FINDING", "rationale": "fixed"}]}) + "\n", encoding="utf-8")
        prompt = build_prompt(self.root, contract_path=self.contract)
        self.assertIn("B001: old bug", prompt)
        self.assertIn("ACCEPT_FINDING", prompt)
        self.assertNotIn("raw chat", prompt.lower())

    def test_prompt_enforces_english_reviewer_channel(self):
        self._prepare()
        prompt = build_prompt(self.root, contract_path=self.contract)
        self.assertIn("Reviewer-facing communication is English-only", prompt)
        self.assertIn("Respond entirely in English", prompt)
        self.assertIn("Conduct the review and write the final response in English only", prompt)

    def test_private_pr_inaccessibility_is_not_itself_a_human_decision_trigger(self):
        self._prepare()
        prompt = build_prompt(self.root, contract_path=self.contract)
        self.assertIn("Direct access to a private GitHub PR is optional corroboration", prompt)
        self.assertIn("Do not return NEEDS_HUMAN_DECISION merely because the PR URL is private", prompt)
        self.assertIn("private repository/PR URL is inaccessible or returns 404", prompt)


if __name__ == "__main__":
    unittest.main()
