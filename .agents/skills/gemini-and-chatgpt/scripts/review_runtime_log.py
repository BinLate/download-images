#!/usr/bin/env python3
"""Append-only reviewer browser runtime logging and bounded timeout checks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_GATE_TIMEOUT_SEC = 900
DEFAULT_PHASE_TIMEOUT_SEC = 120
DEFAULT_MAX_ATTEMPTS = 3


def _utc_now(epoch: float | None = None) -> str:
    value = time.time() if epoch is None else epoch
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _base_record(event: str, phase: str | None, attempt: int | None, now: float) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ts": _utc_now(now),
        "epoch": now,
        "event": event,
    }
    if phase:
        record["phase"] = phase
    if attempt is not None:
        record["attempt"] = attempt
    return record


def start_session(
    log_path: Path,
    state_path: Path,
    *,
    gate_timeout_sec: int = DEFAULT_GATE_TIMEOUT_SEC,
    phase_timeout_sec: int = DEFAULT_PHASE_TIMEOUT_SEC,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    target_head_sha: str = "",
    pr_url: str = "",
    now: float | None = None,
) -> dict[str, Any]:
    current = time.time() if now is None else now
    state = {
        "started_epoch": current,
        "started_at": _utc_now(current),
        "status": "RUNNING",
        "gate_timeout_sec": gate_timeout_sec,
        "phase_timeout_sec": phase_timeout_sec,
        "max_attempts": max_attempts,
        "current_phase": None,
        "phase_started_epoch": None,
        "last_event_epoch": current,
        "target_head_sha": target_head_sha,
        "pr_url": pr_url,
    }
    _atomic_write_json(state_path, state)
    record = _base_record("SESSION_START", None, None, current)
    record.update({
        "gate_timeout_sec": gate_timeout_sec,
        "phase_timeout_sec": phase_timeout_sec,
        "max_attempts": max_attempts,
        "target_head_sha": target_head_sha,
        "pr_url": pr_url,
    })
    _append_jsonl(log_path, record)
    return state


def log_event(
    log_path: Path,
    state_path: Path,
    *,
    event: str,
    phase: str | None = None,
    attempt: int | None = None,
    status: str | None = None,
    message: str = "",
    details: dict[str, Any] | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    current = time.time() if now is None else now
    state = _read_json(state_path)
    if not state:
        raise RuntimeError("review runtime session has not been started")
    record = _base_record(event, phase, attempt, current)
    if status:
        record["status"] = status
    if message:
        record["message"] = message
    if details:
        record["details"] = details
    _append_jsonl(log_path, record)
    state["last_event_epoch"] = current
    if event == "PHASE_START":
        state["current_phase"] = phase
        state["phase_started_epoch"] = current
        state["current_attempt"] = attempt
    if status in {"BLOCKED", "FAIL", "PASS"} and event == "SESSION_FINISH":
        state["status"] = status
        state["finished_epoch"] = current
        state["finished_at"] = _utc_now(current)
    _atomic_write_json(state_path, state)
    return record


def check_limits(
    log_path: Path,
    state_path: Path,
    *,
    phase: str,
    attempt: int,
    now: float | None = None,
    phase_timeout_override: int | None = None,
    gate_timeout_override: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    current = time.time() if now is None else now
    state = _read_json(state_path)
    if not state:
        raise RuntimeError("review runtime session has not been started")
    gate_elapsed = current - float(state["started_epoch"])
    phase_started = state.get("phase_started_epoch")
    phase_elapsed = current - float(phase_started) if phase_started is not None else 0.0
    gate_timeout = int(gate_timeout_override if gate_timeout_override is not None else state.get("gate_timeout_sec", DEFAULT_GATE_TIMEOUT_SEC))
    phase_timeout = int(phase_timeout_override if phase_timeout_override is not None else state.get("phase_timeout_sec", DEFAULT_PHASE_TIMEOUT_SEC))
    max_attempts = int(state.get("max_attempts", DEFAULT_MAX_ATTEMPTS))

    reason = ""
    if attempt > max_attempts:
        reason = f"attempt {attempt} exceeds max_attempts {max_attempts}"
    elif gate_elapsed > gate_timeout:
        reason = f"overall Gate E elapsed {gate_elapsed:.1f}s exceeds {gate_timeout}s"
    elif phase_elapsed > phase_timeout:
        reason = f"phase {phase} elapsed {phase_elapsed:.1f}s exceeds {phase_timeout}s"

    result = {
        "ok": not bool(reason),
        "phase": phase,
        "attempt": attempt,
        "gate_elapsed_sec": round(gate_elapsed, 3),
        "phase_elapsed_sec": round(phase_elapsed, 3),
        "gate_timeout_sec": gate_timeout,
        "phase_timeout_sec": phase_timeout,
        "max_attempts": max_attempts,
        "reason": reason,
    }
    event = _base_record("LIMIT_CHECK", phase, attempt, current)
    event.update(result)
    _append_jsonl(log_path, event)
    state["last_event_epoch"] = current
    if reason:
        state["status"] = "BLOCKED"
        state["blocked_reason"] = reason
        state["blocked_at"] = _utc_now(current)
    _atomic_write_json(state_path, state)
    return not bool(reason), result


def summarize(log_path: Path, state_path: Path, *, tail: int = 40) -> dict[str, Any]:
    state = _read_json(state_path)
    rows: list[dict[str, Any]] = []
    if log_path.exists():
        for line in log_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    if tail > 0:
        rows = rows[-tail:]
    return {"state": state, "events": rows, "event_count_returned": len(rows)}


def _parse_details(value: str) -> dict[str, Any]:
    if not value:
        return {}
    path = Path(value)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("details must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", default="review-runtime.jsonl")
    parser.add_argument("--state", default="review-runtime-state.json")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--gate-timeout-sec", type=int, default=DEFAULT_GATE_TIMEOUT_SEC)
    start.add_argument("--phase-timeout-sec", type=int, default=DEFAULT_PHASE_TIMEOUT_SEC)
    start.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    start.add_argument("--target-head-sha", default="")
    start.add_argument("--pr-url", default="")

    event = sub.add_parser("event")
    event.add_argument("--event", required=True)
    event.add_argument("--phase")
    event.add_argument("--attempt", type=int)
    event.add_argument("--status")
    event.add_argument("--message", default="")
    event.add_argument("--details", default="", help="JSON object or path to JSON file")

    check = sub.add_parser("check")
    check.add_argument("--phase", required=True)
    check.add_argument("--attempt", type=int, required=True)
    check.add_argument("--phase-timeout-sec", type=int)
    check.add_argument("--gate-timeout-sec", type=int)

    summary = sub.add_parser("summary")
    summary.add_argument("--tail", type=int, default=40)

    finish = sub.add_parser("finish")
    finish.add_argument("--status", choices=["PASS", "BLOCKED", "FAIL"], required=True)
    finish.add_argument("--message", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_path = Path(args.log)
    state_path = Path(args.state)
    try:
        if args.command == "start":
            payload = start_session(
                log_path,
                state_path,
                gate_timeout_sec=args.gate_timeout_sec,
                phase_timeout_sec=args.phase_timeout_sec,
                max_attempts=args.max_attempts,
                target_head_sha=args.target_head_sha,
                pr_url=args.pr_url,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "event":
            payload = log_event(
                log_path,
                state_path,
                event=args.event,
                phase=args.phase,
                attempt=args.attempt,
                status=args.status,
                message=args.message,
                details=_parse_details(args.details),
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "check":
            ok, payload = check_limits(
                log_path, state_path, phase=args.phase, attempt=args.attempt,
                phase_timeout_override=args.phase_timeout_sec, gate_timeout_override=args.gate_timeout_sec,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if ok else 2
        if args.command == "summary":
            payload = summarize(log_path, state_path, tail=args.tail)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command == "finish":
            payload = log_event(
                log_path,
                state_path,
                event="SESSION_FINISH",
                status=args.status,
                message=args.message,
            )
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if args.status == "PASS" else 2
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"review runtime log error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
