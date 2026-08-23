#!/usr/bin/env python3
"""Fail-closed verifier for ChatGPT Web paste/send target integrity.

The browser agent must capture a small JSON snapshot from page DOM immediately before
review prompt insertion and again immediately before Send. This verifier rejects any
snapshot where the browser document is not focused, the expected reviewer URL changed,
or the exact ChatGPT composer is not the active DOM element.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ALLOWED_HOSTS = {"chatgpt.com", "www.chatgpt.com"}
ALLOWED_COMPOSER_TAGS = {"textarea", "div"}
ALLOWED_SELECTORS = {"#prompt-textarea", "[data-testid='prompt-textarea']", '[contenteditable="true"]'}


class TargetVerificationError(RuntimeError):
    pass


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "https":
        raise TargetVerificationError("review page must use https")
    host = (parts.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise TargetVerificationError(f"unexpected review host: {host or '<missing>'}")
    # Fragment is not identity-bearing for the reviewer page. Keep query/path exact.
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    return urlunsplit(("https", netloc, path, parts.query, ""))


def _require_bool(data: dict, key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise TargetVerificationError(f"{key} must be a boolean")
    return value


def verify_target(snapshot: dict, expected_url: str) -> dict:
    if not isinstance(snapshot, dict):
        raise TargetVerificationError("snapshot must be a JSON object")

    current_url = snapshot.get("page_url")
    if not isinstance(current_url, str) or not current_url.strip():
        raise TargetVerificationError("page_url is required")
    normalized_expected = normalize_url(expected_url)
    normalized_current = normalize_url(current_url)
    if normalized_current != normalized_expected:
        raise TargetVerificationError(
            f"review page URL changed (expected {normalized_expected}, got {normalized_current})"
        )

    if not _require_bool(snapshot, "document_has_focus"):
        raise TargetVerificationError(
            "ChatGPT document does not have focus; address bar/browser chrome may be active"
        )
    if not _require_bool(snapshot, "composer_found"):
        raise TargetVerificationError("ChatGPT composer was not found")
    if not _require_bool(snapshot, "composer_visible"):
        raise TargetVerificationError("ChatGPT composer is not visible")
    if not _require_bool(snapshot, "composer_enabled"):
        raise TargetVerificationError("ChatGPT composer is not enabled")
    if not _require_bool(snapshot, "active_is_composer"):
        raise TargetVerificationError(
            "exact ChatGPT composer is not document.activeElement; paste/send is forbidden"
        )

    selector = snapshot.get("composer_selector")
    if not isinstance(selector, str) or selector not in ALLOWED_SELECTORS:
        raise TargetVerificationError(f"unrecognized composer selector: {selector!r}")

    tag = snapshot.get("composer_tag")
    if not isinstance(tag, str) or tag.lower() not in ALLOWED_COMPOSER_TAGS:
        raise TargetVerificationError(f"unexpected composer tag: {tag!r}")

    role = snapshot.get("composer_role")
    contenteditable = snapshot.get("composer_contenteditable")
    role_ok = isinstance(role, str) and role.lower() == "textbox"
    editable_ok = contenteditable is True or (
        isinstance(contenteditable, str) and contenteditable.lower() == "true"
    )
    if not (role_ok or editable_ok or tag.lower() == "textarea"):
        raise TargetVerificationError("composer is not an editable textbox")

    return {
        "ok": True,
        "page_url": normalized_current,
        "composer_selector": selector,
        "document_has_focus": True,
        "active_is_composer": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify ChatGPT reviewer composer target integrity")
    parser.add_argument("--snapshot", required=True, help="JSON DOM/focus snapshot path")
    parser.add_argument("--expected-url", required=True, help="Expected fresh reviewer page URL")
    parser.add_argument("--json", dest="json_path", help="Optional JSON result output")
    args = parser.parse_args()

    try:
        raw = Path(args.snapshot).read_text(encoding="utf-8")
        snapshot = json.loads(raw)
        result = verify_target(snapshot, args.expected_url)
        exit_code = 0
    except (OSError, json.JSONDecodeError, TargetVerificationError) as exc:
        result = {"ok": False, "error": str(exc)}
        exit_code = 2

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
