#!/usr/bin/env python3
"""Fail-closed verifier for ChatGPT reviewer composer attachment cleanliness.

Text equality alone is insufficient because a clipboard image/file can be attached while
reviewer-prompt.txt is also present in the composer. The browser agent must capture a
small JSON snapshot of the composer surface after insertion and again immediately before
Send. This verifier authorizes Send only when the draft contains zero attachments and no
pending/error upload state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


class AttachmentVerificationError(RuntimeError):
    pass


def _require_bool(data: dict, key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise AttachmentVerificationError(f"{key} must be a boolean")
    return value


def _require_count(data: dict, key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AttachmentVerificationError(f"{key} must be a non-negative integer")
    return value


def verify_attachments(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict):
        raise AttachmentVerificationError("snapshot must be a JSON object")

    attachment_count = _require_count(snapshot, "attachment_count")
    pending_upload_count = _require_count(snapshot, "pending_upload_count")
    has_attachment_preview = _require_bool(snapshot, "has_attachment_preview")
    has_attachment_remove_control = _require_bool(snapshot, "has_attachment_remove_control")
    has_pending_upload = _require_bool(snapshot, "has_pending_upload")
    has_upload_error = _require_bool(snapshot, "has_upload_error")

    problems = []
    if attachment_count:
        problems.append(f"attachment_count={attachment_count}")
    if pending_upload_count:
        problems.append(f"pending_upload_count={pending_upload_count}")
    if has_attachment_preview:
        problems.append("attachment preview is present")
    if has_attachment_remove_control:
        problems.append("attachment remove control is present")
    if has_pending_upload:
        problems.append("an upload is still pending")
    if has_upload_error:
        problems.append("an upload error is present")

    if problems:
        raise AttachmentVerificationError(
            "review draft contains or may contain non-text attachment state: " + "; ".join(problems)
        )

    return {
        "ok": True,
        "attachment_count": 0,
        "pending_upload_count": 0,
        "has_attachment_preview": False,
        "has_attachment_remove_control": False,
        "has_pending_upload": False,
        "has_upload_error": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify ChatGPT reviewer draft has no attachments/uploads")
    parser.add_argument("--snapshot", required=True, help="JSON composer attachment snapshot path")
    parser.add_argument("--json", dest="json_path", help="Optional JSON result output")
    args = parser.parse_args()

    try:
        snapshot = json.loads(Path(args.snapshot).read_text(encoding="utf-8"))
        result = verify_attachments(snapshot)
        exit_code = 0
    except (OSError, json.JSONDecodeError, AttachmentVerificationError) as exc:
        result = {"ok": False, "error": str(exc)}
        exit_code = 2

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
