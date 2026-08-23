from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_normal_transport_has_no_typed_fallback():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "Reviewer transport must be clipboard-free and typing-free" in text
    assert "review_round.py --root ." in text
    assert "already-open Antigravity Chrome" in text
    assert "Do not fall back to typing" in text
    assert "Shift+Enter" in text
    assert "MUST NOT use Windows clipboard" in text


def test_workspace_rule_forbids_browser_subagent_typing_and_clipboard():
    text = (ROOT / "scripts" / "install_agents_rule.ps1").read_text(encoding="utf-8")
    assert "run exactly one normal review command" in text
    assert "Never use Windows clipboard, Ctrl+V, simulated typing, Shift+Enter, or Enter" in text
    assert "do not fall back to typing" in text


def test_typed_fallback_runtime_removed_from_bundle():
    assert not (ROOT / "scripts" / "typed_review_plan.py").exists()
    assert not (ROOT / "tests" / "test_typed_review_plan.py").exists()


def test_clipboard_helpers_remain_removed():
    for name in ["copy_review_prompt.ps1", "arm_review_clipboard.ps1", "paste_review_prompt.ps1"]:
        assert not (ROOT / "scripts" / name).exists()


def test_workflow_uses_single_command_and_existing_browser_first():
    text = (ROOT / "references" / "workflow.md").read_text(encoding="utf-8")
    assert "review_round.py --root ." in text
    assert "already-open Antigravity Chrome" in text
    assert "No typed fallback is permitted" in text
    assert "Wait at most 300 seconds" in text
