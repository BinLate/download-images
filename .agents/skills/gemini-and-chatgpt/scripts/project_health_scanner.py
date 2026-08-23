#!/usr/bin/env python3
"""Project Health / QA Scanner for C5.

This script reads the project-context.json to automatically detect
lint, typecheck, test, and build commands. It maps them into the JSON 
array format expected by the Verification Gate.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from context_store import load_context
from project_context_scan import freshness as context_freshness


def scan_health(root: str | Path, require_all: bool = True) -> list[dict[str, Any]]:
    """Scan the project context and return a list of verification checks."""
    context = load_context(root)
    status = context_freshness(root, context)
    if status["status"] != "FRESH":
        # If stale, we still return the checks, but maybe log a warning?
        # The orchestrator will refresh if needed before planner, 
        # but for health scan we just use what's there.
        pass

    commands_dict = context.get("commands", {})
    checks = []
    
    # We want a logical order: lint -> typecheck -> test -> build
    order = ["lint", "typecheck", "test", "build"]
    
    for kind in order:
        commands = commands_dict.get(kind, [])
        for i, cmd_str in enumerate(commands):
            check_id = kind if len(commands) == 1 else f"{kind}-{i+1}"
            checks.append({
                "id": check_id,
                "command": cmd_str,
                "required": require_all
            })
            
    return checks


def main() -> None:
    ap = argparse.ArgumentParser(description="Project Health / QA Scanner")
    ap.add_argument("--root", default=".")
    ap.add_argument("--optional", action="store_true", help="Make detected checks optional")
    args = ap.parse_args()

    try:
        checks = scan_health(args.root, require_all=not args.optional)
        print(json.dumps(checks, indent=2, ensure_ascii=False))
    except Exception as exc:
        raise SystemExit(f"qa scanner error: {exc}") from exc


if __name__ == "__main__":
    main()
