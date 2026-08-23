import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
import sys
sys.path.insert(0, str(SCRIPTS))

from orchestrator import (
    OrchestratorError,
    begin_implementation,
    begin_verification,
    classify_and_route,
    enter_review,
    initialize_task,
    mark_plan_ready,
    record_review_verdict,
    run_verification,
    start_task,
    sync_delivery,
    verify_candidate,
)
from plan_store import save_plan
from task_store import load_task
from verification_gate import CheckSpec

SHA1 = "a" * 40
SHA2 = "b" * 40


def standard_plan(task_id):
    return {
        "schema_version": "2.0.0",
        "task_id": task_id,
        "goal": "Implement feature safely",
        "in_scope": ["feature"],
        "out_of_scope": [],
        "constraints": [],
        "assumptions": [],
        "acceptance_criteria": ["tests pass"],
        "risk_level": "MEDIUM",
        "risk_notes": [],
        "release_constraints": [],
        "work_items": [
            {"id": "W1", "objective": "implement", "owner_role": "BUILDER", "scope_hints": [], "dependencies": [], "verification": ["tests"], "status": "PENDING"}
        ],
    }


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_simple_routes_directly_to_implementation(self):
        initialize_task(self.root, "Fix typo in README", "Fix typo")
        state = classify_and_route(self.root)
        self.assertEqual(state["classification"]["complexity_tier"], "SIMPLE")
        self.assertEqual(state["lifecycle"]["current_state"], "IMPLEMENTING")


    def test_start_combines_init_and_classification_for_one_file_workflow_task(self):
        state = start_task(
            self.root,
            "Tạo file review-live-test.txt rồi chạy full GitHub/ChatGPT review workflow",
            "Create review live test",
            estimated_files=1,
            estimated_components=1,
        )
        self.assertEqual(state["classification"]["complexity_tier"], "SIMPLE")
        self.assertFalse(state["classification"]["planner_required"])
        self.assertEqual(state["lifecycle"]["current_state"], "IMPLEMENTING")

    def test_verify_candidate_combines_begin_and_gate(self):
        start_task(self.root, "Fix typo in README", "Fix typo", estimated_files=1, estimated_components=1)
        checks = [CheckSpec("test", "FOCUSED_TEST", "python -c \"print('ok')\"", True)]
        state, records = verify_candidate(self.root, SHA1, checks, branch="ai/fix", changed_files=["README.md"])
        self.assertEqual(state["verification"]["overall_status"], "PASS")
        self.assertEqual(state["lifecycle"]["current_state"], "PR_PREPARING")
        self.assertEqual(len(records), 1)

    def test_standard_requires_plan_before_implementation(self):
        state = initialize_task(self.root, "Add product search feature", "Add search")
        state = classify_and_route(self.root, estimated_files=4)
        self.assertEqual(state["lifecycle"]["current_state"], "PLANNING")
        plan = standard_plan(state["identity"]["id"])
        save_plan(self.root, plan)
        state = mark_plan_ready(self.root)
        self.assertEqual(state["lifecycle"]["current_state"], "PLAN_READY")
        state = begin_implementation(self.root)
        self.assertEqual(state["lifecycle"]["current_state"], "IMPLEMENTING")

    def test_high_risk_routes_to_human_precheck(self):
        initialize_task(self.root, "Change authentication authorization model", "Auth model")
        state = classify_and_route(self.root)
        self.assertEqual(state["lifecycle"]["current_state"], "HUMAN_DECISION")

    def test_verification_pass_routes_to_pr_preparing(self):
        initialize_task(self.root, "Fix typo in README", "Fix typo")
        classify_and_route(self.root)
        begin_verification(self.root, SHA1)
        checks = [CheckSpec("test", "FOCUSED_TEST", "python -c \"print('ok')\"", True)]
        state, _ = run_verification(self.root, SHA1, checks)
        self.assertEqual(state["verification"]["overall_status"], "PASS")
        self.assertEqual(state["lifecycle"]["current_state"], "PR_PREPARING")

    def _prepare_review(self, max_rounds=5):
        initialize_task(self.root, "Fix typo in README", "Fix typo", max_rounds=max_rounds)
        classify_and_route(self.root)
        begin_verification(self.root, SHA1)
        run_verification(self.root, SHA1, [CheckSpec("test", "FOCUSED_TEST", "python -c \"print('ok')\"", True)])
        sync_delivery(self.root, head_sha=SHA1, pr_number=7, pr_url="https://github.com/o/r/pull/7", pr_state="OPEN", repository="o/r", base_branch="main", head_branch="ai/fix")
        return enter_review(self.root)

    def test_review_round_increments_on_review_entry(self):
        state = self._prepare_review()
        self.assertEqual(state["review"]["round"], 1)
        self.assertEqual(state["review"]["current_target_sha"], SHA1)

    def test_delivery_head_must_equal_verified_candidate(self):
        initialize_task(self.root, "Fix typo in README", "Fix typo")
        classify_and_route(self.root)
        begin_verification(self.root, SHA1)
        run_verification(self.root, SHA1, [CheckSpec("test", "FOCUSED_TEST", "python -c \"print('ok')\"", True)])
        with self.assertRaises(OrchestratorError):
            sync_delivery(self.root, head_sha=SHA2, pr_number=7, pr_url="https://github.com/o/r/pull/7", pr_state="OPEN")

    def test_request_changes_routes_to_fixing(self):
        self._prepare_review()
        state = record_review_verdict(self.root, "REQUEST_CHANGES", SHA1, findings=[{"id": "F1"}])
        self.assertEqual(state["lifecycle"]["current_state"], "FIXING")
        self.assertFalse(state["review"]["approval_valid"])

    def test_request_changes_at_max_routes_to_limit(self):
        self._prepare_review(max_rounds=1)
        state = record_review_verdict(self.root, "REQUEST_CHANGES", SHA1)
        self.assertEqual(state["lifecycle"]["current_state"], "REVIEW_LIMIT_REACHED")

    def test_approval_routes_to_release_gate_not_merge(self):
        self._prepare_review()
        state = record_review_verdict(self.root, "APPROVED_TO_MERGE", SHA1)
        self.assertEqual(state["lifecycle"]["current_state"], "RELEASE_GATE")
        self.assertEqual(state["release"]["status"], "READY_FOR_HUMAN_RELEASE")
        self.assertEqual(state["release"]["approved_sha"], SHA1)
        self.assertEqual(state["release"]["merge_policy"], "human_only")

    def test_new_head_after_fix_consumes_next_round_only_at_review(self):
        self._prepare_review()
        record_review_verdict(self.root, "REQUEST_CHANGES", SHA1)
        begin_verification(self.root, SHA2)
        state = load_task(self.root)
        self.assertEqual(state["review"]["round"], 1)
        run_verification(self.root, SHA2, [CheckSpec("test2", "FOCUSED_TEST", "python -c \"print('ok')\"", True)])
        sync_delivery(self.root, head_sha=SHA2, pr_number=7, pr_url="https://github.com/o/r/pull/7", pr_state="OPEN")
        state = enter_review(self.root)
        self.assertEqual(state["review"]["round"], 2)
        self.assertEqual(state["review"]["current_target_sha"], SHA2)
        self.assertFalse(state["review"]["approval_valid"])

    def test_wrong_review_sha_fails_closed(self):
        self._prepare_review()
        with self.assertRaises(OrchestratorError):
            record_review_verdict(self.root, "APPROVED_TO_MERGE", SHA2)


if __name__ == "__main__":
    unittest.main()
