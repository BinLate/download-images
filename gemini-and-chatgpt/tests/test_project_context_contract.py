from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ProjectContextContractTests(unittest.TestCase):
    def test_installer_requires_c2_runtime(self):
        text = (ROOT / "INSTALL-ANTIGRAVITY.bat").read_text(encoding="utf-8")
        self.assertIn("scripts\\context_store.py", text)
        self.assertIn("scripts\\project_context_scan.py", text)

    def test_skill_declares_freshness_and_secret_safety(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Project Context v2", text)
        self.assertIn("STALE", text)
        self.assertIn("environment **variable names only**", text)
        self.assertIn("lazy context slices", text)

    def test_agents_rule_requires_nontrivial_context(self):
        text = (ROOT / "scripts" / "install_agents_rule.ps1").read_text(encoding="utf-8")
        self.assertIn("For STANDARD/COMPLEX tasks", text)
        self.assertIn("project_context_scan.py", text)

if __name__ == "__main__":
    unittest.main()
