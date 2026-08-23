import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReviewRuntimeContractTests(unittest.TestCase):
    def test_skill_uses_prepare_browser_subagent_finalize(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("prepare -> one Browser Subagent review -> finalize", text)
        self.assertIn("one `browser_subagent` task", text)
        self.assertIn("click the visible Send button exactly once", text)
        self.assertNotIn("review_round.py transport --root .", text)

    def test_workflow_browser_subagent_owns_send_and_response(self):
        text = (ROOT / "references" / "workflow.md").read_text(encoding="utf-8")
        self.assertIn("Browser Subagent owns the entire browser interaction", text)
        self.assertIn("return the entire verbatim response", text)
        self.assertIn("no active `transport` phase", text)

    def test_direct_fill_is_disabled_compatibility_stub(self):
        text = (ROOT / "scripts" / "direct_fill_review_prompt.ps1").read_text(encoding="utf-8")
        self.assertIn("LEGACY_TRANSPORT_DISABLED", text)
        self.assertNotIn("Input.insertText", text)
        self.assertNotIn("Start-Process", text)

    def test_workspace_rule_does_not_split_browser_and_send(self):
        text = (ROOT / "scripts" / "install_agents_rule.ps1").read_text(encoding="utf-8")
        self.assertIn("Invoke ONE Antigravity `browser_subagent` task", text)
        self.assertIn("click the visible Send button exactly once", text)
        self.assertIn("NO active `transport` phase", text)
        self.assertNotIn("review_round.py transport --root .", text)


if __name__ == "__main__":
    unittest.main()
