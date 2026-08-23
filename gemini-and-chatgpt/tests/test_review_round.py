from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "review_round.py"


def test_review_round_consolidates_full_review_lifecycle():
    text = SCRIPT.read_text(encoding="utf-8")
    for token in [
        "gh", "pr", "view", "headRefOid", "Verification Gate must be PASS",
        "build_prompt", "write_manifest", "direct_fill_review_prompt.ps1",
        "response_received", "parse_review", "record_review_verdict",
    ]:
        assert token in text


def test_review_round_keeps_artifacts_out_of_project_root():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"reviews" / f"round-{round_no:02d}"' in text
    for name in ["pr-diff.patch", "reviewer-prompt.txt", "reviewer-response.txt", "review-result.json"]:
        assert name in text


def test_review_round_handles_one_time_login_without_incrementing_again():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'current not in {"PR_PREPARING", "REVIEWING"}' in text
    assert 'if current == "PR_PREPARING"' in text
    assert 'if transport.returncode == 4' in text
    assert 'REVIEWER_LOGIN_REQUIRED' in text


def test_review_round_has_no_typed_fallback_or_browser_subagent_path():
    text = SCRIPT.read_text(encoding="utf-8").lower()
    assert "typed_review_plan" not in text
    assert "ctrl+v" not in text
    assert "shift+enter" not in text
    assert "browser_press_key" not in text


def test_review_round_writes_compact_action_log_without_logging_subprocess():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "append_action" in text
    assert "gemini-chatgpt-actions.log" not in text  # path is centralized in action_log.py
    assert 'stage="REVIEW_COMMAND"' in text
    assert 'stage="REVIEW_TRANSPORT"' in text
    assert '"action_log"' in text


def test_review_round_uses_one_github_metadata_query_and_local_diff():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '["gh", "pr", "view"' in text
    assert '["gh", "repo", "view"' not in text
    assert '["gh", "pr", "diff"' not in text
    assert '["git", "diff", "--binary", "--find-renames"' in text
    assert "_repository_from_pr_url" in text


def test_review_round_logs_transport_self_healing_metrics():
    text = SCRIPT.read_text(encoding="utf-8")
    for token in ["review_target_reused", "composer_resets", "insertion_attempts"]:
        assert token in text


def test_review_round_is_idempotent_at_release_gate_and_does_not_force_new_review():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'status": "ALREADY_APPROVED"' in text
    assert 'current_state") != "RELEASE_GATE"' in text
    assert "no new ChatGPT review was started" in text
    assert "_already_approved(root, args.task_id)" in text


def test_review_round_suppresses_automatic_repeat_after_transport_failure():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'review-round-guard.json' in text
    assert 'BLOCKED_RETRY_SUPPRESSED' in text
    assert '--retry-blocked' in text
    assert '_write_review_guard' in text
    assert '_clear_review_guard' in text


def test_review_guard_matches_only_same_task_sha_and_round(tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import review_round as rr

    sha = "a" * 40
    state = {
        "identity": {"id": "T-test"},
        "review": {"round": 2, "current_target_sha": sha},
    }
    rr._write_review_guard(tmp_path, state=state, head=sha, error="transport failed")
    blocked = rr._same_blocked_attempt(tmp_path, state)
    assert blocked is not None
    assert blocked["target_head_sha"] == sha

    changed = {
        "identity": {"id": "T-test"},
        "review": {"round": 3, "current_target_sha": sha},
    }
    assert rr._same_blocked_attempt(tmp_path, changed) is None


def test_already_approved_returns_success_without_starting_browser(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import review_round as rr

    sha = "b" * 40
    state = {
        "identity": {"id": "T-approved"},
        "lifecycle": {"current_state": "RELEASE_GATE"},
        "release": {"approved_sha": sha},
        "verification": {"candidate_sha": sha, "overall_status": "PASS"},
        "delivery": {"head_sha": sha},
        "review": {
            "current_target_sha": sha,
            "current_verdict": "APPROVED_TO_MERGE",
            "approval_valid": True,
        },
    }
    monkeypatch.setattr(rr, "load_task", lambda root, task_id=None: state)
    monkeypatch.setattr(rr, "_run_json", lambda cmd, root: {
        "number": 1,
        "url": "https://github.com/example/repo/pull/1",
        "headRefName": "feat/x",
        "headRefOid": sha,
        "baseRefName": "main",
        "baseRefOid": "c" * 40,
        "state": "OPEN",
    })
    monkeypatch.setattr(rr, "_run", lambda cmd, root: sha)
    result = rr._already_approved(tmp_path, None)
    assert result is not None
    assert result["status"] == "ALREADY_APPROVED"
    assert result["target_head_sha"] == sha


def test_review_round_forces_utf8_for_windows_subprocess_output():
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.count('encoding="utf-8"') >= 2
    assert text.count('errors="replace"') >= 2
    assert 'proc = subprocess.run(' in text
    assert 'transport = subprocess.run(' in text
