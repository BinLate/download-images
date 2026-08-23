import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
NOW = "2026-08-19T06:00:00Z"
SHA = "0123456789abcdef0123456789abcdef01234567"
TASK_ID = "T-20260819-001-schema-baseline"


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def validate(schema_name, instance):
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return errors


class SchemaContractTests(unittest.TestCase):
    def project_context(self):
        return {
            "schema_version": "2.1.0",
            "project": {"name": "demo", "root": "/repo", "repository": "owner/demo"},
            "stack": {"languages": [{"name": "Python", "file_count": 2}], "package_managers": [], "frameworks": ["pytest"]},
            "modules": [{"path": "src", "source_file_count": 2, "language_hints": ["Python"]}],
            "architecture": {"summary": "", "components": ["src"], "boundaries": [], "constraints": []},
            "conventions": {"coding": [], "testing": [], "git": []},
            "commands": {"install": [], "lint": ["python -m unittest"], "typecheck": [], "test": ["python -m unittest discover -s tests"], "build": []},
            "decisions": [],
            "known_risks": [],
            "environment": {"required_variable_names": ["GITHUB_TOKEN_NAME_ONLY"]},
            "provenance": {
                "commands": {"install": [], "lint": ["pyproject.toml"], "typecheck": [], "test": ["pyproject.toml"], "build": []},
                "stack": ["pyproject.toml"], "modules": ["src/a.py", "src/b.py"], "conventions": [], "environment": [], "redactions": []
            },
            "discovery": {"generated_at": NOW, "fingerprint": "0" * 64, "inventory_fingerprint": "1" * 64, "source_file_count": 2, "sources": [], "scan_limit": 10000, "files_observed": 2},
            "updated_at": NOW,
        }

    def task_state(self):
        return {
            "schema_version": "2.0.0",
            "identity": {"id": TASK_ID, "original_request": "Add schemas", "normalized_title": "schema baseline", "created_at": NOW, "updated_at": NOW},
            "classification": {"kind": "MAINTENANCE", "complexity_tier": "STANDARD", "risk_level": "LOW", "score": 2, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
            "requirements": {"goal": "Create contracts", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": ["Schemas validate"], "release_constraints": [], "assumptions": []},
            "plan": {"required": True, "status": "READY", "plan_path": ".ai/tasks/x/plan.json", "work_item_count": 1, "completed_count": 0, "current_work_item": "W1"},
            "roles": {"active": ["BUILDER"], "completed": ["PLANNER"]},
            "lifecycle": {"current_state": "PLAN_READY", "previous_state": "PLANNING", "state_entered_at": NOW, "transition_reason": "plan created", "resume_state": None, "local_repair_attempts": 0},
            "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": ["W1"]},
            "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": ".ai/tasks/x/verification.jsonl"},
            "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": None, "pr_url": None, "pr_state": None, "head_sha": None, "last_push_at": None},
            "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": ".ai/tasks/x/review-history.jsonl", "approval_valid": False},
            "decisions": [],
            "blockers": [],
            "release": {"status": "PENDING", "merge_policy": "human_only", "human_required": False, "human_reason": None, "approved_sha": None},
            "checkpoint": {"latest_path": None, "latest_at": None},
        }

    def plan(self):
        return {
            "schema_version": "2.0.0",
            "task_id": TASK_ID,
            "goal": "Add contracts",
            "in_scope": ["schemas/"],
            "out_of_scope": ["runtime orchestration"],
            "constraints": ["Preserve v1 behavior"],
            "assumptions": ["Python is available"],
            "acceptance_criteria": ["Tests pass"],
            "risk_level": "LOW",
            "risk_notes": ["Additive change"],
            "work_items": [{"id": "W1", "owner_role": "BUILDER", "objective": "Create files", "scope_hints": ["schemas/"], "dependencies": [], "verification": ["schema tests"], "status": "READY"}],
            "release_constraints": [],
        }

    def evidence(self):
        return {
            "schema_version": "2.0.0",
            "task_id": TASK_ID,
            "candidate_sha": SHA,
            "check_id": "unit-tests",
            "category": "REGRESSION_TEST",
            "required": True,
            "status": "PASS",
            "started_at": NOW,
            "completed_at": NOW,
            "exit_code": 0,
            "command": "python -m unittest discover -s tests",
            "scope": ["tests/"],
            "summary": "all tests passed",
            "reason": None,
        }

    def checkpoint(self):
        return {
            "schema_version": "2.0.0",
            "task_id": TASK_ID,
            "created_at": NOW,
            "reason": "STATE_TRANSITION",
            "lifecycle": {"current_state": "VERIFYING", "previous_state": "IMPLEMENTING", "resume_state": None},
            "implementation": {"branch": "feat/x", "candidate_sha": SHA, "changed_files": ["x.py"]},
            "verification": {"overall_status": "PASS", "candidate_sha": SHA, "evidence_ledger_path": ".ai/tasks/x/verification.jsonl"},
            "delivery": {"pr_number": None, "pr_url": None, "head_sha": None},
            "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "approval_valid": False},
            "blockers": [],
            "resume_hint": "continue to PR_PREPARING",
        }

    def test_valid_examples_pass(self):
        fixtures = [
            ("project-context.schema.json", self.project_context()),
            ("task-state.schema.json", self.task_state()),
            ("plan.schema.json", self.plan()),
            ("verification-evidence.schema.json", self.evidence()),
            ("checkpoint.schema.json", self.checkpoint()),
        ]
        for schema, payload in fixtures:
            with self.subTest(schema=schema):
                self.assertEqual(validate(schema, payload), [])

    def test_missing_required_field_fails(self):
        payload = self.task_state()
        del payload["identity"]
        self.assertTrue(validate("task-state.schema.json", payload))

    def test_invalid_enum_fails(self):
        payload = self.task_state()
        payload["classification"]["complexity_tier"] = "GIANT"
        self.assertTrue(validate("task-state.schema.json", payload))

    def test_project_context_does_not_allow_secret_value_storage(self):
        payload = self.project_context()
        payload["environment"]["values"] = {"GITHUB_TOKEN": "secret"}
        errors = validate("project-context.schema.json", payload)
        self.assertTrue(errors)
        self.assertTrue(any("Additional properties are not allowed" in e.message for e in errors))

    def test_verification_failure_requires_reason(self):
        payload = self.evidence()
        payload["status"] = "FAIL"
        payload["exit_code"] = 1
        payload["reason"] = None
        self.assertTrue(validate("verification-evidence.schema.json", payload))

    def test_full_sha_contract_rejects_abbreviated_candidate(self):
        payload = self.evidence()
        payload["candidate_sha"] = "0123456"
        self.assertTrue(validate("verification-evidence.schema.json", payload))

    def test_skipped_plan_item_requires_reason(self):
        payload = self.plan()
        payload["work_items"][0]["status"] = "SKIPPED_WITH_REASON"
        self.assertTrue(validate("plan.schema.json", payload))
        payload["work_items"][0]["skip_reason"] = "Not applicable to this repository"
        self.assertEqual(validate("plan.schema.json", payload), [])

    def test_received_state_allows_unclassified_sentinel(self):
        payload = self.task_state()
        payload["classification"]["kind"] = "UNKNOWN"
        payload["classification"]["complexity_tier"] = "UNCLASSIFIED"
        payload["classification"]["risk_level"] = "UNKNOWN"
        payload["classification"]["score"] = 0
        payload["classification"]["planner_required"] = False
        payload["lifecycle"]["current_state"] = "RECEIVED"
        payload["lifecycle"]["previous_state"] = None
        self.assertEqual(validate("task-state.schema.json", payload), [])


if __name__ == "__main__":
    unittest.main()
