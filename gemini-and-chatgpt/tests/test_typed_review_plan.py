import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("typed_review_plan", ROOT / "scripts" / "typed_review_plan.py")
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MOD)


def sample(body="line one\n\nline three"):
    return (
        "=== GEMINI_CHATGPT_REVIEW_BEGIN ===\n"
        "PROMPT_ID: abc123\n"
        "TARGET_HEAD_SHA: " + "a" * 40 + "\n"
        + body + "\n"
        "=== GEMINI_CHATGPT_REVIEW_END ==="
    )


def test_plan_never_embeds_newline_in_type_text():
    plan = MOD.build_plan(sample())
    assert plan["transport"] == "TYPED_FALLBACK_LINE_SAFE"
    for action in plan["actions"]:
        if action["action"] == "TYPE_TEXT":
            assert "\n" not in action["text"]
            assert "\r" not in action["text"]


def test_newlines_become_shift_enter_only():
    text = sample("A\nB")
    plan = MOD.build_plan(text)
    typed = [a for a in plan["actions"] if a["action"] == "TYPE_TEXT"]
    assert any(a["text"] == "A" for a in typed)
    assert any(a["text"] == "B" for a in typed)
    assert all(a["action"] in {"TYPE_TEXT", "SHIFT_ENTER"} for a in plan["actions"])
    assert sum(a["action"] == "SHIFT_ENTER" for a in plan["actions"]) == text.count("\n")


def test_preserves_identity():
    plan = MOD.build_plan(sample())
    assert plan["prompt_id"] == "abc123"
    assert plan["target_head_sha"] == "a" * 40
