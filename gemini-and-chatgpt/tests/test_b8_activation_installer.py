import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class B8ActivationInstallerTests(unittest.TestCase):
    def test_skill_declares_natural_language_auto_activation(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not require the user to say `Use gemini-and-chatgpt`", text)
        self.assertIn("scripts/orchestrator.py", text)
        self.assertIn("automatic merge", text.lower())
        self.assertIn("human_only", text)

    def test_agents_rule_contains_one_managed_block_literal(self):
        text = (ROOT / "scripts" / "install_agents_rule.ps1").read_text(encoding="utf-8")
        block = re.search(r"\$block\s*=\s*@'(?P<body>.*?)'@", text, re.S)
        self.assertIsNotNone(block)
        body = block.group("body")
        self.assertEqual(body.count("<!-- gemini-and-chatgpt:begin -->"), 1)
        self.assertEqual(body.count("<!-- gemini-and-chatgpt:end -->"), 1)
        self.assertIn("fresh ChatGPT conversation", body)
        self.assertIn("Automatic merge remains OFF", body)
        self.assertIn("exact full 40-character PR HEAD SHA", body)

    def test_installer_refreshes_and_copies_complete_v2_skill(self):
        text = (ROOT / "INSTALL-ANTIGRAVITY.bat").read_text(encoding="utf-8", errors="replace")
        self.assertIn('if /I "%TOOL_DIR%"=="%SKILL_DEST%"', text)
        self.assertIn('rmdir /S /Q "%SKILL_DEST%"', text)
        self.assertIn('for %%D in (agents references schemas scripts) do (', text)
        for required in [
            "scripts\\orchestrator.py",
            "scripts\\verification_gate.py",
            "scripts\\review_prompt.py",
            "scripts\\verify_review_transport.py",
            "scripts\\verify_review_target.py",
            "scripts\\direct_fill_review_prompt.ps1",
            "references\\review-contract.md",
            "schemas\\task-state.schema.json",
        ]:
            self.assertIn(required, text)

    def test_yes_no_prompts_show_enter_default(self):
        text = (ROOT / "INSTALL-ANTIGRAVITY.bat").read_text(encoding="utf-8", errors="replace")
        self.assertRegex(text, r"Initialize Git now\? \[Y/n\] \(default Y\):")
        self.assertRegex(text, r"Install GitHub CLI now with winget\? \[Y/n\] \(default Y\):")
        self.assertIn('if "!INITGIT!"=="" set "INITGIT=Y"', text)
        self.assertIn('if "!INSTALLGH!"=="" set "INSTALLGH=Y"', text)

    def test_installation_docs_preserve_human_release_gate(self):
        text = (ROOT / "references" / "installation.md").read_text(encoding="utf-8")
        self.assertIn("Automatic merge is OFF by default", text)
        self.assertIn("fresh ChatGPT conversation", text)
        self.assertIn("OPEN", text)
        self.assertIn("40-character", text)

    def test_no_awf_global_installer_is_added(self):
        installer = (ROOT / "INSTALL-ANTIGRAVITY.bat").read_text(encoding="utf-8", errors="replace").lower()
        installation = (ROOT / "references" / "installation.md").read_text(encoding="utf-8").lower()
        self.assertNotIn("global_workflows", installer)
        self.assertIn("do not install awf globally", installation)


if __name__ == "__main__":
    unittest.main()
