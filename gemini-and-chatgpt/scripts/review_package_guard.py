#!/usr/bin/env python3
"""Immutable package guard for reviewer prompt transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

BEGIN = "=== GEMINI_CHATGPT_REVIEW_BEGIN ==="
END = "=== GEMINI_CHATGPT_REVIEW_END ==="
PROMPT_ID_RE = re.compile(r"(?m)^PROMPT_ID:\s*([0-9a-f]{24})\s*$")
HEAD_RE = re.compile(r"(?m)^TARGET_HEAD_SHA:\s*([0-9a-fA-F]{40})\s*$")
REQUIRED_SECTIONS = (
    "# Independent Review Package",
    "## Language policy",
    "## Task identity",
    "## Goal",
    "## In scope",
    "## Out of scope",
    "## Acceptance criteria",
    "## Material constraints and assumptions",
    "## Implementation summary",
    "## Planner work-item summary",
    "## Pull request identity",
    "## Verification evidence bound to TARGET_HEAD_SHA",
    "## Prior blocking findings / dispositions",
    "## Changed-file / diff context",
    "## Reviewer contract",
    "## Binding instruction",
)

class ReviewPackageError(RuntimeError):
    pass


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


def validate_full_package(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    lines = normalized.split("\n")
    if lines.count(BEGIN) != 1 or lines.count(END) != 1:
        raise ReviewPackageError("review package BEGIN/END markers must appear exactly once")
    if not lines or lines[0] != BEGIN:
        raise ReviewPackageError("review package must begin with the transport BEGIN marker")
    if END not in lines or lines.index(END) >= len(lines) - 2:
        raise ReviewPackageError("review package END marker/footer is incomplete")
    prompt_ids = PROMPT_ID_RE.findall(normalized)
    heads = [x.lower() for x in HEAD_RE.findall(normalized)]
    if len(prompt_ids) != 2 or prompt_ids[0] != prompt_ids[1]:
        raise ReviewPackageError("review package requires exactly two matching PROMPT_ID values")
    if len(heads) != 2 or heads[0] != heads[1]:
        raise ReviewPackageError("review package requires exactly two matching TARGET_HEAD_SHA values")
    for section in REQUIRED_SECTIONS:
        if lines.count(section) != 1:
            raise ReviewPackageError(f"required review section missing or duplicated: {section}")
    if len(lines) < 40:
        raise ReviewPackageError("review package is implausibly short; refusing truncated/minimal transport source")
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return {
        "package_kind": "gemini_chatgpt_independent_review_v2",
        "manifest_version": 1,
        "prompt_id": prompt_ids[0],
        "target_head_sha": heads[0],
        "canonical_sha256": digest,
        "canonical_chars": len(normalized),
        "canonical_lines": len(lines),
        "required_sections": list(REQUIRED_SECTIONS),
    }


def manifest_path_for(prompt_path: str | Path) -> Path:
    p = Path(prompt_path)
    return p.with_suffix(".manifest.json")


def write_manifest(prompt_path: str | Path, manifest_path: str | Path | None = None) -> dict[str, Any]:
    prompt_path = Path(prompt_path)
    data = validate_full_package(prompt_path.read_text(encoding="utf-8"))
    out = Path(manifest_path) if manifest_path else manifest_path_for(prompt_path)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def verify_manifest(prompt_path: str | Path, manifest_path: str | Path | None = None) -> dict[str, Any]:
    prompt_path = Path(prompt_path)
    manifest_file = Path(manifest_path) if manifest_path else manifest_path_for(prompt_path)
    if not manifest_file.exists():
        raise ReviewPackageError(f"review package manifest missing: {manifest_file}")
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewPackageError(f"corrupt review package manifest: {exc}") from exc
    actual = validate_full_package(prompt_path.read_text(encoding="utf-8"))
    keys = ("package_kind", "manifest_version", "prompt_id", "target_head_sha", "canonical_sha256", "canonical_chars", "canonical_lines")
    mismatches = [k for k in keys if manifest.get(k) != actual.get(k)]
    if mismatches:
        raise ReviewPackageError("reviewer-prompt.txt no longer matches immutable manifest: " + ", ".join(mismatches))
    return actual


def main() -> int:
    ap = argparse.ArgumentParser(description="Create/verify immutable reviewer prompt manifest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("manifest", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--prompt", required=True)
        p.add_argument("--manifest")
    args = ap.parse_args()
    try:
        data = write_manifest(args.prompt, args.manifest) if args.cmd == "manifest" else verify_manifest(args.prompt, args.manifest)
    except (OSError, ReviewPackageError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps({"ok": True, **{k: data[k] for k in ("prompt_id", "target_head_sha", "canonical_sha256", "canonical_chars", "canonical_lines")}}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
