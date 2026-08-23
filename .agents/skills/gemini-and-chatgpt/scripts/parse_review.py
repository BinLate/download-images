#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VERDICTS = {'APPROVED_TO_MERGE', 'REQUEST_CHANGES', 'NEEDS_HUMAN_DECISION'}
FULL_SHA_RE = re.compile(r'^[0-9a-fA-F]{40}$')


def parse(text: str) -> dict:
    # 1. Search for TARGET_HEAD_SHA (with optional markdown formatting like ** or `)
    sha_m = re.search(r'^\s*(?:\*\*)?TARGET_HEAD_SHA:?(?:\*\*)?\s*[`*]*([^\s`*]+)[`*]*\s*$', text, re.M)
    if not sha_m:
        sha_m = re.search(r'(?:\*\*)?TARGET_HEAD_SHA:?(?:\*\*)?\s*[`*]*([0-9a-fA-F]{40})[`*]*', text)

    # 2. Search for VERDICT (with optional markdown formatting)
    verdict_m = re.search(r'^\s*(?:\*\*)?VERDICT:?(?:\*\*)?\s*[`*]*(APPROVED_TO_MERGE|REQUEST_CHANGES|NEEDS_HUMAN_DECISION)[`*]*\s*$', text, re.M)
    if not verdict_m:
        verdict_m = re.search(r'(?:\*\*)?VERDICT:?(?:\*\*)?\s*[`*]*(APPROVED_TO_MERGE|REQUEST_CHANGES|NEEDS_HUMAN_DECISION)[`*]*', text)

    if not sha_m or not verdict_m:
        return {'ok': False, 'verdict': 'NEEDS_HUMAN_DECISION', 'error': 'Malformed reviewer output', 'target_head_sha': None}

    sha = sha_m.group(1).strip()
    if not FULL_SHA_RE.fullmatch(sha):
        return {'ok': False, 'verdict': 'NEEDS_HUMAN_DECISION', 'error': 'TARGET_HEAD_SHA must be exactly 40 hexadecimal characters', 'target_head_sha': sha.lower()}

    verdict = verdict_m.group(1).strip()
    blockers = re.findall(r'^\s*-\s*\[(B\d+)\]\s*(.+)$', text, re.M)
    non_blockers = re.findall(r'^\s*-\s*\[(N\d+)\]\s*(.+)$', text, re.M)

    return {
        'ok': True,
        'verdict': verdict,
        'target_head_sha': sha.lower(),
        'blocking_findings': [{'id': i, 'text': t.strip()} for i, t in blockers if t.strip().upper() != 'NONE'],
        'non_blocking_findings': [{'id': i, 'text': t.strip()} for i, t in non_blockers if t.strip().upper() != 'NONE'],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('--json', dest='json_out')
    ap.add_argument('--expect-head')
    args = ap.parse_args()
    text = Path(args.input).read_text(encoding='utf-8')
    result = parse(text)
    if args.expect_head:
        expected = args.expect_head.lower()
        if not FULL_SHA_RE.fullmatch(expected):
            result = {'ok': False, 'verdict': 'NEEDS_HUMAN_DECISION', 'error': 'Expected HEAD SHA must be exactly 40 hexadecimal characters', 'target_head_sha': result.get('target_head_sha'), 'expected_head_sha': expected}
        elif result.get('ok') and result.get('target_head_sha') != expected:
            result = {'ok': False, 'verdict': 'NEEDS_HUMAN_DECISION', 'error': 'HEAD SHA mismatch', 'target_head_sha': result.get('target_head_sha'), 'expected_head_sha': expected}
    out = json.dumps(result, indent=2, sort_keys=True)
    print(out)
    if args.json_out:
        Path(args.json_out).write_text(out + '\n', encoding='utf-8')
    raise SystemExit(0 if result.get('ok') else 2)


if __name__ == '__main__':
    main()

