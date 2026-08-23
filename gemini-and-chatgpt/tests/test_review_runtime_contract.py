import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReviewRuntimeContractTests(unittest.TestCase):
    def test_skill_uses_atomic_review_round(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("review_round.py", text)
        self.assertIn("CDP", text)

    def test_direct_fill_implements_real_cdp_insert(self):
        text = (ROOT / "scripts" / "direct_fill_review_prompt.ps1").read_text(encoding="utf-8")
        self.assertIn("Input.insertText", text)
        self.assertIn("DIRECT_FILL_CDP", text)

    def test_workspace_rule_uses_atomic_review(self):
        text = (ROOT / "scripts" / "install_agents_rule.ps1").read_text(encoding="utf-8")
        self.assertIn("review_round.py", text)


if __name__ == "__main__":
    unittest.main()
