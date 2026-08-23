#!/usr/bin/env python3
"""Fail-closed verifier for reviewer prompt transport into ChatGPT Web."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

from review_package_guard import verify_manifest

BEGIN = "=== GEMINI_CHATGPT_REVIEW_BEGIN ==="
END = "=== GEMINI_CHATGPT_REVIEW_END ==="
PROMPT_ID_RE = re.compile(r"(?m)^PROMPT_ID:\s*([0-9a-f]{24})\s*$")
HEAD_RE = re.compile(r"(?m)^TARGET_HEAD_SHA:\s*([0-9a-fA-F]{40})\s*$")


class TransportVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TransportIdentity:
    prompt_id: str
    target_head_sha: str


def normalize_text(text: str) -> str:
    """Normalize only transport-irrelevant newline differences."""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def parse_identity(text: str) -> TransportIdentity:
    normalized = normalize_text(text)
    lines = normalized.split("\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        raise TransportVerificationError("transport BEGIN/END markers must appear exactly once")
    begin_index = lines.index(BEGIN)
    end_index = lines.index(END)
    if begin_index != 0 or end_index >= len(lines) - 2:
        raise TransportVerificationError("transport markers are not in the required boundary positions")
    if end_index <= begin_index:
        raise TransportVerificationError("transport END marker precedes BEGIN marker")

    prompt_ids = PROMPT_ID_RE.findall(normalized)
    if len(prompt_ids) != 2 or prompt_ids[0] != prompt_ids[1]:
        raise TransportVerificationError("exactly two matching PROMPT_ID values are required")

    heads = [value.lower() for value in HEAD_RE.findall(normalized)]
    if len(heads) != 2 or heads[0] != heads[1]:
        raise TransportVerificationError("exactly two matching full TARGET_HEAD_SHA values are required")

    if lines[1] != f"PROMPT_ID: {prompt_ids[0]}" or lines[2].lower() != f"target_head_sha: {heads[0]}":
        raise TransportVerificationError("transport identity header is malformed")
    if lines[-2] != f"PROMPT_ID: {prompt_ids[0]}" or lines[-1].lower() != f"target_head_sha: {heads[0]}":
        raise TransportVerificationError("transport identity footer is malformed")

    return TransportIdentity(prompt_id=prompt_ids[0], target_head_sha=heads[0])


def verify_transport(expected_text: str, actual_text: str) -> TransportIdentity:
    expected_identity = parse_identity(expected_text)
    actual_identity = parse_identity(actual_text)
    if actual_identity != expected_identity:
        raise TransportVerificationError(
            "composer transport identity does not match reviewer-prompt.txt "
            f"(expected PROMPT_ID={expected_identity.prompt_id} HEAD={expected_identity.target_head_sha}, "
            f"got PROMPT_ID={actual_identity.prompt_id} HEAD={actual_identity.target_head_sha})"
        )
    if normalize_text(actual_text) != normalize_text(expected_text):
        raise TransportVerificationError(
            "composer text does not exactly match reviewer-prompt.txt after newline normalization"
        )
    return expected_identity


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify ChatGPT composer text against reviewer-prompt.txt")
    parser.add_argument("--expected", required=True, help="Path to reviewer-prompt.txt")
    parser.add_argument("--actual", required=True, help="Path containing composer read-back text")
    parser.add_argument("--json", dest="json_path", help="Optional JSON result path")
    parser.add_argument("--manifest", help="Immutable reviewer package manifest; defaults beside --expected")
    args = parser.parse_args()

    try:
        package = verify_manifest(args.expected, args.manifest)
        expected = Path(args.expected).read_text(encoding="utf-8")
        actual = Path(args.actual).read_text(encoding="utf-8")
        identity = verify_transport(expected, actual)
        result = {
            "ok": True,
            "prompt_id": identity.prompt_id,
            "target_head_sha": identity.target_head_sha,
            "canonical_sha256": package["canonical_sha256"],
            "canonical_chars": package["canonical_chars"],
            "canonical_lines": package["canonical_lines"],
        }
        exit_code = 0
    except (OSError, TransportVerificationError) as exc:
        result = {"ok": False, "error": str(exc)}
        exit_code = 2

    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
