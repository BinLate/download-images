from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_requires_zero_attachments_before_send():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "zero attachments/uploads" in text
    assert "verify exact readback/hash/HEAD plus zero attachments/uploads" in text
    assert "clicks the Send button" in text


def test_workflow_requires_zero_attachments_before_send():
    text = (ROOT / "references" / "workflow.md").read_text(encoding="utf-8")
    assert "zero attachments/pending uploads" in text
    assert "require exact text/hash equality and zero attachments/uploads" in text
    assert "Click the ChatGPT Send button through the DOM" in text


def test_installer_keeps_diagnostic_attachment_verifier_available():
    text = (ROOT / "INSTALL-ANTIGRAVITY.bat").read_text(encoding="utf-8")
    assert "scripts\\verify_review_attachments.py" in text
