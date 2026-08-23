import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT = (ROOT / "SKILL.md").read_text(encoding="utf-8")


class SkillInvariantTests(unittest.TestCase):
    def test_natural_language_auto_activation_is_preserved(self):
        self.assertIn("Do not require the user to say `Use gemini-and-chatgpt`", TEXT)
        self.assertIn("automatic activation layer", TEXT)

    def test_review_round_cap_is_preserved(self):
        self.assertIn("review round reaches 5 without approval", TEXT)

    def test_auto_merge_is_off_by_default(self):
        self.assertIn("Do not merge automatically unless the user explicitly enabled automatic merge", TEXT)

    def test_exact_head_review_is_required_by_policy(self):
        self.assertIn("exact current HEAD SHA", TEXT)
        self.assertIn("old approval is invalid", TEXT)


if __name__ == "__main__":
    unittest.main()
