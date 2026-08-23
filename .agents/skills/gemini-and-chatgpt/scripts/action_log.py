#!/usr/bin/env python3
"""Low-overhead append-only action logging for gemini-and-chatgpt.

The logger is intentionally in-process: normal workflow code imports it and writes
one compact line per meaningful action. It must never cause an extra shell command
or browser inspection merely for logging.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _paths(root: str | Path) -> tuple[Path, Path]:
    base = Path(root).resolve() / ".ai"
    base.mkdir(parents=True, exist_ok=True)
    return base / "gemini-chatgpt-actions.log", base / "gemini-chatgpt-actions.jsonl"


def _clean(value: Any, limit: int = 700) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def format_command(parts: Iterable[Any]) -> str:
    out: list[str] = []
    for part in parts:
        text = str(part)
        if any(ch.isspace() for ch in text) or '"' in text:
            text = '"' + text.replace('"', '\\"') + '"'
        out.append(text)
    return " ".join(out)


def append_action(
    root: str | Path,
    *,
    stage: str,
    status: str,
    action: str,
    command: str | None = None,
    duration_ms: int | None = None,
    detail: Any = None,
) -> None:
    text_path, jsonl_path = _paths(root)
    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "timestamp": ts,
        "stage": str(stage),
        "status": str(status),
        "action": str(action),
    }
    if command:
        payload["command"] = command
    if duration_ms is not None:
        payload["duration_ms"] = int(duration_ms)
    if detail not in (None, "", {}, []):
        payload["detail"] = detail

    with jsonl_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    parts = [f"[{ts}]", str(status).upper(), str(stage), "-", _clean(action)]
    if duration_ms is not None:
        parts.append(f"({int(duration_ms)} ms)")
    if command:
        parts.append("cmd=" + _clean(command, 1200))
    if detail not in (None, "", {}, []):
        if isinstance(detail, (dict, list)):
            detail_text = json.dumps(detail, ensure_ascii=False, sort_keys=True)
        else:
            detail_text = str(detail)
        parts.append("detail=" + _clean(detail_text, 1200))
    with text_path.open("a", encoding="utf-8") as fh:
        fh.write(" ".join(parts) + "\n")


def action_log_path(root: str | Path) -> Path:
    return _paths(root)[0]
