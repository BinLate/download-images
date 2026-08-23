import copy
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from plan_store import PlanStoreError, derive_ready, load_plan, render_markdown, save_plan, update_work_item_status, validate_plan
from task_classifier import apply_classification, classify_task
from task_store import create_task, load_task, save_task

TASK_ID = "T-20260819-901-plan-store"


def base_plan():
    return {
        "schema_version": "2.0.0",
        "task_id": TASK_ID,
        "goal": "Implement deterministic planner graph",
        "in_scope": ["scripts/plan_store.py"],
        "out_of_scope": ["Verification Gate"],
        "constraints": ["Preserve v1 compatibility"],
        "assumptions": ["Python standard library is available"],
        "acceptance_criteria": ["Plan graph is acyclic", "Markdown projection is deterministic"],
        "risk_level": "MEDIUM",
        "risk_notes": ["Planning state becomes durable"],
        "work_items": [
            {"id": "W1", "owner_role": "BUILDER", "objective": "Create plan store", "scope_hints": ["scripts/"], "dependencies": [], "verification": ["unit tests"], "status": "PENDING"},
            {"id": "W2", "owner_role": "VERIFIER", "objective": "Verify graph behavior", "scope_hints": ["tests/"], "dependencies": ["W1"], "verification": ["regression suite"], "status": "PENDING"},
        ],
        "release_constraints": ["No runtime activation in B4"],
    }


class PlanStoreTests(unittest.TestCase):
    def prepare_task(self, root):
        state = create_task(root, "Implement planner graph", "planner-graph", task_id=TASK_ID)
        state = apply_classification(state, classify_task("Add planner task graph feature", estimated_files=4))
        save_task(root, state)
        return state

    def test_validate_and_derive_initial_ready(self):
        plan = derive_ready(base_plan())
        self.assertEqual(plan["work_items"][0]["status"], "READY")
        self.assertEqual(plan["work_items"][1]["status"], "PENDING")

    def test_cycle_is_rejected(self):
        plan = base_plan()
        plan["work_items"][0]["dependencies"] = ["W2"]
        with self.assertRaisesRegex(PlanStoreError, "cycle"):
            validate_plan(plan)

    def test_unknown_dependency_is_rejected(self):
        plan = base_plan()
        plan["work_items"][1]["dependencies"] = ["W99"]
        with self.assertRaisesRegex(PlanStoreError, "unknown dependencies"):
            validate_plan(plan)

    def test_markdown_projection_is_deterministic(self):
        plan = derive_ready(base_plan())
        a = render_markdown(plan)
        b = render_markdown(copy.deepcopy(plan))
        self.assertEqual(a, b)
        self.assertIn("W1", a)
        self.assertIn("Acceptance criteria", a)

    def test_save_plan_updates_task_state(self):
        with tempfile.TemporaryDirectory() as td:
            self.prepare_task(td)
            pjson, pmd = save_plan(td, base_plan())
            self.assertTrue(pjson.exists())
            self.assertTrue(pmd.exists())
            state = load_task(td, TASK_ID)
            self.assertTrue(state["plan"]["required"])
            self.assertEqual(state["plan"]["status"], "READY")
            self.assertEqual(state["plan"]["work_item_count"], 2)
            self.assertEqual(state["plan"]["current_work_item"], "W1")
            self.assertEqual(state["requirements"]["acceptance_criteria"], base_plan()["acceptance_criteria"])

    def test_progress_unlocks_dependencies_and_syncs_state(self):
        with tempfile.TemporaryDirectory() as td:
            self.prepare_task(td)
            save_plan(td, base_plan())
            update_work_item_status(td, TASK_ID, "W1", "DONE")
            plan = load_plan(td, TASK_ID)
            self.assertEqual(plan["work_items"][1]["status"], "READY")
            state = load_task(td, TASK_ID)
            self.assertEqual(state["implementation"]["work_items_completed"], ["W1"])
            self.assertEqual(state["plan"]["current_work_item"], "W2")

    def test_cannot_start_item_with_incomplete_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            self.prepare_task(td)
            save_plan(td, base_plan())
            with self.assertRaisesRegex(PlanStoreError, "incomplete dependencies"):
                update_work_item_status(td, TASK_ID, "W2", "IN_PROGRESS")

    def test_skipped_requires_reason_and_unlocks_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            self.prepare_task(td)
            save_plan(td, base_plan())
            with self.assertRaisesRegex(PlanStoreError, "skip_reason"):
                update_work_item_status(td, TASK_ID, "W1", "SKIPPED_WITH_REASON")
            update_work_item_status(td, TASK_ID, "W1", "SKIPPED_WITH_REASON", skip_reason="Repository capability not applicable")
            plan = load_plan(td, TASK_ID)
            self.assertEqual(plan["work_items"][1]["status"], "READY")

    def test_simple_task_rejects_full_plan(self):
        with tempfile.TemporaryDirectory() as td:
            state = create_task(td, "Fix README typo", "readme-typo", task_id=TASK_ID)
            state = apply_classification(state, classify_task("Fix README typo", estimated_files=1))
            save_task(td, state)
            plan = base_plan()
            plan["risk_level"] = "LOW"
            with self.assertRaisesRegex(PlanStoreError, "reserved"):
                save_plan(td, plan)

    def test_plan_risk_must_match_classification(self):
        with tempfile.TemporaryDirectory() as td:
            self.prepare_task(td)
            plan = base_plan()
            plan["risk_level"] = "HIGH"
            with self.assertRaisesRegex(PlanStoreError, "risk_level"):
                save_plan(td, plan)


if __name__ == "__main__":
    unittest.main()
