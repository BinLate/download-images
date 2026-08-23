import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import context_store
import task_store
import verification_gate

SHA_A = "a" * 40
SHA_B = "b" * 40


class VerificationGateTests(unittest.TestCase):
    def make_task(self, root: Path):
        return task_store.create_task(root, "test verification", "test verification")

    def test_check_spec_requires_reason_when_no_command(self):
        with self.assertRaises(verification_gate.VerificationGateError):
            verification_gate.CheckSpec.from_dict({"check_id": "x", "category": "TEST"})

    def test_passing_command_creates_pass_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            rec = verification_gate.run_check(
                verification_gate.CheckSpec("ok", "CUSTOM", f'"{sys.executable}" -c "print(123)"'),
                project_root=td, task_id="T-20260819-001-x", candidate_sha=SHA_A,
            )
            self.assertEqual(rec["status"], "PASS")
            self.assertEqual(rec["candidate_sha"], SHA_A)
            self.assertEqual(rec["exit_code"], 0)

    def test_failing_command_creates_fail_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            rec = verification_gate.run_check(
                verification_gate.CheckSpec("bad", "CUSTOM", f'"{sys.executable}" -c "import sys; sys.exit(3)"'),
                project_root=td, task_id="T-20260819-001-x", candidate_sha=SHA_A,
            )
            self.assertEqual(rec["status"], "FAIL")
            self.assertEqual(rec["exit_code"], 3)
            self.assertIn("code 3", rec["reason"])

    def test_required_skip_is_partial_not_pass(self):
        rec = {
            "schema_version": "2.0.0", "task_id": "T-20260819-001-x", "candidate_sha": SHA_A,
            "check_id": "lint", "category": "LINT", "required": True, "status": "SKIPPED",
            "started_at": "2026-08-19T00:00:00+00:00", "completed_at": "2026-08-19T00:00:01+00:00",
            "exit_code": None, "command": None, "scope": [], "summary": "not run", "reason": "not configured",
        }
        self.assertEqual(verification_gate.aggregate_status([rec]), "PARTIAL")

    def test_required_blocked_is_blocked(self):
        rec = self._record("BLOCKED", required=True)
        self.assertEqual(verification_gate.aggregate_status([rec]), "BLOCKED")

    def test_required_fail_is_fail(self):
        self.assertEqual(verification_gate.aggregate_status([self._record("FAIL", required=True)]), "FAIL")

    def test_optional_failure_makes_partial(self):
        rows = [self._record("PASS", required=True, check_id="required"), self._record("FAIL", required=False, check_id="optional")]
        self.assertEqual(verification_gate.aggregate_status(rows), "PARTIAL")

    def test_empty_evidence_is_blocked(self):
        self.assertEqual(verification_gate.aggregate_status([]), "BLOCKED")

    def test_apply_pass_rejects_required_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = self.make_task(root)
            rec = self._record("SKIPPED", required=True)
            with self.assertRaises(verification_gate.VerificationGateError):
                verification_gate.apply_verification_summary(state, candidate_sha=SHA_A, records=[rec], overall_status="PASS")

    def test_apply_rejects_mixed_candidate_sha(self):
        with tempfile.TemporaryDirectory() as td:
            state = self.make_task(Path(td))
            rec = self._record("PASS", required=True)
            rec["candidate_sha"] = SHA_B
            with self.assertRaises(verification_gate.VerificationGateError):
                verification_gate.apply_verification_summary(state, candidate_sha=SHA_A, records=[rec])

    def test_verify_task_appends_ledger_and_updates_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = self.make_task(root)
            checks = [verification_gate.CheckSpec("unit", "FOCUSED_TEST", f'"{sys.executable}" -c "print(\'ok\')"', True)]
            updated, records = verification_gate.verify_task(root, candidate_sha=SHA_A, checks=checks, task_id=state["identity"]["id"])
            self.assertEqual(updated["verification"]["overall_status"], "PASS")
            self.assertEqual(updated["verification"]["candidate_sha"], SHA_A)
            ledger = verification_gate.evidence_path(root, state["identity"]["id"])
            lines = ledger.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["check_id"], "unit")
            reloaded = task_store.load_task(root, state["identity"]["id"])
            self.assertEqual(reloaded["implementation"]["candidate_sha"], SHA_A)

    def test_second_run_appends_instead_of_rewriting(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = self.make_task(root)
            checks = [verification_gate.CheckSpec("unit", "FOCUSED_TEST", f'"{sys.executable}" -c "pass"', True)]
            verification_gate.verify_task(root, candidate_sha=SHA_A, checks=checks, task_id=state["identity"]["id"])
            verification_gate.verify_task(root, candidate_sha=SHA_A, checks=checks, task_id=state["identity"]["id"])
            ledger = verification_gate.evidence_path(root, state["identity"]["id"])
            self.assertEqual(len(ledger.read_text(encoding="utf-8").strip().splitlines()), 2)

    def test_new_candidate_replaces_current_summary_but_keeps_old_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = self.make_task(root)
            checks = [verification_gate.CheckSpec("unit", "FOCUSED_TEST", f'"{sys.executable}" -c "pass"', True)]
            verification_gate.verify_task(root, candidate_sha=SHA_A, checks=checks, task_id=state["identity"]["id"])
            current = task_store.load_task(root, state["identity"]["id"])
            current["implementation"]["candidate_sha"] = None
            task_store.save_task(root, current)
            updated, _ = verification_gate.verify_task(root, candidate_sha=SHA_B, checks=checks, task_id=state["identity"]["id"])
            self.assertEqual(updated["verification"]["candidate_sha"], SHA_B)
            lines = verification_gate.evidence_path(root, state["identity"]["id"]).read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual([json.loads(v)["candidate_sha"] for v in lines], [SHA_A, SHA_B])

    def test_candidate_mismatch_with_implementation_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state = self.make_task(root)
            state["implementation"]["candidate_sha"] = SHA_A
            task_store.save_task(root, state)
            checks = [verification_gate.CheckSpec("unit", "FOCUSED_TEST", f'"{sys.executable}" -c "pass"', True)]
            with self.assertRaises(verification_gate.VerificationGateError):
                verification_gate.verify_task(root, candidate_sha=SHA_B, checks=checks, task_id=state["identity"]["id"])

    def test_default_checks_standard_missing_build_is_required_skip(self):
        with tempfile.TemporaryDirectory() as td:
            ctx = context_store.new_context(td, "x")
            ctx = context_store.add_command(ctx, "test", "python -m unittest")
            checks = verification_gate.default_checks_from_context(ctx, complexity_tier="STANDARD", risk_level="MEDIUM")
            by_id = {c.check_id: c for c in checks}
            self.assertTrue(by_id["lint-missing"].required)
            self.assertTrue(by_id["build-missing"].required)
            self.assertIsNone(by_id["build-missing"].command)

    def _record(self, status, *, required=True, check_id="x"):
        return {
            "schema_version": "2.0.0", "task_id": "T-20260819-001-x", "candidate_sha": SHA_A,
            "check_id": check_id, "category": "CUSTOM", "required": required, "status": status,
            "started_at": "2026-08-19T00:00:00+00:00", "completed_at": "2026-08-19T00:00:01+00:00",
            "exit_code": 0 if status == "PASS" else None, "command": "echo x", "scope": [], "summary": status,
            "reason": None if status == "PASS" else status.lower(),
        }


if __name__ == "__main__":
    unittest.main()
