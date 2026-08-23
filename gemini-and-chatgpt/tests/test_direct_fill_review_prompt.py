from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "direct_fill_review_prompt.ps1"


def test_direct_fill_prefers_existing_antigravity_browser_then_has_safe_fallback():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Find-ExistingDebugBrowser" in text
    assert "ANTIGRAVITY_EXISTING_CDP" in text
    assert "Ensure-ReviewerBrowser" in text
    assert "DIRECT_FILL_CDP" in text
    assert "DEDICATED_REVIEWER_CDP_FALLBACK" in text
    assert "--remote-debugging-port=" in text
    assert "REVIEWER_LOGIN_REQUIRED" in text
    ensure = text.split("function Ensure-ReviewerBrowser", 1)[1].split("function Receive-CdpMessage", 1)[0]
    assert "Find-ExistingDebugBrowser" in ensure
    assert "Ensure-DedicatedReviewerBrowser" in ensure
    dedicated = text.split("function Ensure-DedicatedReviewerBrowser", 1)[1].split("function Ensure-ReviewerBrowser", 1)[0]
    assert "Find-ChromeExecutable" in dedicated


def test_powershell_51_chrome_lookup_never_indexes_a_pipeline_unboxed_string():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "foreach ($candidate in $candidates)" in text
    assert "return [string]$candidate" in text
    assert "if ($candidates.Count -gt 0) { return $candidates[0] }" not in text


def test_direct_fill_is_one_operation_clipboard_and_typing_free():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Input.insertText" in text
    assert "send.click()" in text
    assert "composer text does not exactly match immutable prompt" in text
    assert "attachment/upload state is not clean" in text
    lowered = text.lower()
    for forbidden in ["ctrl+v", "ctrl+a", "get-clipboard", "set-clipboard", "sendkeys", "shift+enter", "type_text", "selectall"]:
        assert forbidden not in lowered


def test_direct_fill_waits_for_and_saves_completed_response():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "ResponseTimeoutSec = 300" in text
    assert '[data-message-author-role="assistant"]' in text
    assert "response_received = $true" in text
    assert "REVIEWER_RESPONSE_TIMEOUT" in text


def test_direct_fill_checks_immutable_package_and_zero_attachments():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Verify-ImmutablePackage" in text
    assert "canonical_sha256" in text
    assert "canonical_lines" in text
    assert "PROMPT_ID binding invalid" in text
    assert "TARGET_HEAD_SHA binding invalid" in text
    assert "attachment_present" in text or "attachment/upload state is not clean" in text


def test_direct_fill_reuses_one_reviewer_target_instead_of_opening_tabs_each_attempt():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "$ReviewerTargetStatePath" in text
    assert "function Get-ReviewerTarget" in text
    assert "review_target_reused" in text
    assert "Page.navigate" in text
    assert "New chat" not in text
    # New target creation remains only a one-time fallback when no reusable ChatGPT target exists.
    assert text.count("/json/new?") == 1


def test_direct_fill_self_heals_stale_or_mismatched_composer_in_place_once():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "function Reset-ComposerDom" in text
    assert "$insertionAttempts -lt 2" in text
    assert "composer_resets" in text
    assert "insertion_attempts" in text
    assert "could not clear stale composer state without keyboard automation" in text
    assert "after one in-place retry" in text


def test_result_hash_does_not_repeat_browser_source_key():
    text = SCRIPT.read_text(encoding="utf-8")
    result_block = text.split("$result = [ordered]@{", 1)[1].split("    }", 1)[0]
    assert result_block.count("browser_source =") == 1


def test_installer_requires_direct_fill_and_review_round():
    text = (ROOT / "INSTALL-ANTIGRAVITY.bat").read_text(encoding="utf-8", errors="replace")
    assert "scripts\\direct_fill_review_prompt.ps1" in text
    assert "scripts\\review_round.py" in text
    assert "scripts\\action_log.py" in text
    assert "typed_review_plan.py" not in text


def test_direct_fill_fails_over_in_process_when_existing_cdp_disappears():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "function Test-CdpList" in text
    assert "function Resolve-ReviewerBrowserTarget" in text
    assert "$script:BrowserFailovers++" in text
    assert "Ensure-DedicatedReviewerBrowser" in text
    assert "browser_failovers" in text


def test_reviewer_target_state_is_bound_to_live_browser_port():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "port = $Port" in text
    assert "[int]$saved.port -eq $Port" in text
    assert "Save-ReviewerTarget $tab $Port $Source" in text


def test_direct_fill_waits_for_dom_readback_to_stabilize_before_retry():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "function Wait-ComposerReadback" in text
    assert "TimeoutMs = 2500" in text
    assert "expected_sha256" in text
    assert "actual_sha256" in text


def test_powershell_interpolated_variables_before_colon_are_braced():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '$Port:' not in text
    assert 'port ${Port}:' in text
