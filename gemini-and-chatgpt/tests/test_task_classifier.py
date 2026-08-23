import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from task_classifier import apply_classification, classify_task
from task_store import new_task_state


class TaskClassifierTests(unittest.TestCase):
    def test_docs_typo_is_simple_low(self):
        c = classify_task("Fix a typo in README documentation", estimated_files=1)
        self.assertEqual(c.kind, "DOCS")
        self.assertEqual(c.complexity_tier, "SIMPLE")
        self.assertEqual(c.risk_level, "LOW")
        self.assertFalse(c.planner_required)

    def test_one_file_bug_is_simple(self):
        c = classify_task("Fix error when email is empty", estimated_files=1)
        self.assertEqual(c.kind, "BUGFIX")
        self.assertEqual(c.complexity_tier, "SIMPLE")

    def test_one_file_task_stays_simple_even_when_full_workflow_is_requested(self):
        c = classify_task(
            "Tạo file review-live-test.txt ở project root với nội dung test. Thực hiện đầy đủ workflow tự động đến khi ChatGPT Web review xong. Không tự merge.",
            estimated_files=1,
            estimated_components=1,
        )
        self.assertEqual(c.complexity_tier, "SIMPLE")
        self.assertFalse(c.planner_required)

    def test_multi_file_bug_is_standard(self):
        c = classify_task("Fix checkout error", estimated_files=4)
        self.assertEqual(c.complexity_tier, "STANDARD")
        self.assertTrue(c.planner_required)
        self.assertIn("MULTI_FILE_SCOPE", c.signals)

    def test_ordinary_feature_is_standard(self):
        c = classify_task("Add product search by name and category", estimated_files=2)
        self.assertEqual(c.kind, "FEATURE")
        self.assertEqual(c.complexity_tier, "STANDARD")

    def test_database_migration_is_complex_and_human_precheck(self):
        c = classify_task("Add database migration to backfill customer status")
        self.assertEqual(c.complexity_tier, "COMPLEX")
        self.assertTrue(c.architect_required)
        self.assertTrue(c.human_precheck_required)
        self.assertIn("DATA_MIGRATION", c.signals)

    def test_auth_change_is_complex_and_human_precheck(self):
        c = classify_task("Change authentication and authorization model for admin users")
        self.assertEqual(c.kind, "SECURITY")
        self.assertEqual(c.complexity_tier, "COMPLEX")
        self.assertTrue(c.human_precheck_required)

    def test_major_dependency_upgrade_is_complex(self):
        c = classify_task("Perform major dependency framework migration to the next major version")
        self.assertEqual(c.kind, "DEPENDENCY")
        self.assertEqual(c.complexity_tier, "COMPLEX")
        self.assertIn("MAJOR_DEPENDENCY", c.signals)

    def test_cross_service_refactor_is_complex(self):
        c = classify_task("Broad refactor across multiple services and service boundaries")
        self.assertEqual(c.complexity_tier, "COMPLEX")
        self.assertTrue(c.architect_required)

    def test_ambiguity_raises_standard_routing_signal(self):
        c = classify_task("Update behavior, not sure what exact output should be", ambiguity=True)
        self.assertIn("AMBIGUOUS_REQUIREMENTS", c.signals)
        self.assertIn(c.complexity_tier, {"STANDARD", "COMPLEX"})

    def test_apply_classification_sets_plan_requirement(self):
        state = new_task_state("T-20260819-900-classifier", "Add search", "add-search")
        c = classify_task("Add search feature", estimated_files=3)
        updated = apply_classification(state, c)
        self.assertEqual(updated["classification"]["complexity_tier"], "STANDARD")
        self.assertTrue(updated["plan"]["required"])
        self.assertEqual(updated["plan"]["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
