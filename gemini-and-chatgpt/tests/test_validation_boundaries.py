from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ValidationBoundaryTests(unittest.TestCase):
    def test_skill_forbids_private_pr_browser_identity_check(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not open GitHub Web merely to verify PR identity or HEAD", text)
        self.assertIn("deterministic `git` + `gh` reconciliation internally", text)

    def test_self_validation_keeps_tool_immutable(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("immutable test infrastructure", text)
        self.assertIn("Do not edit, generate files inside, or patch either copy", text)

    def test_managed_rule_keeps_fail_closed_browser_transport(self):
        text = (ROOT / "scripts" / "install_agents_rule.ps1").read_text(encoding="utf-8")
        self.assertIn("is `BLOCKED`", text)
        self.assertIn("immutable", text)
        self.assertIn("launch a dedicated reviewer", text.lower())
        self.assertIn("clipboard paste", text.lower())


if __name__ == "__main__":
    unittest.main()
