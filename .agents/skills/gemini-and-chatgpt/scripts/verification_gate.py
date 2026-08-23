#!/usr/bin/env python3
"""Central deterministic Verification Gate for gemini-and-chatgpt v2.

The gate executes an explicit set of checks against one immutable candidate
commit SHA, appends per-check evidence to verification.jsonl, and updates the
authoritative task state's verification summary. It never turns a skipped or
blocked required check into PASS.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from task_store import TaskStoreError, load_task, save_task, task_dir, validate_task_state

SCHEMA_VERSION = "2.0.0"
FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
CATEGORIES = {
    "LINT",
    "TYPECHECK",
    "FOCUSED_TEST",
    "REGRESSION_TEST",
    "BUILD",
    "INTEGRATION_SMOKE",
    "CUSTOM",
}
CHECK_STATUSES = {"PASS", "FAIL", "BLOCKED", "SKIPPED"}
OVERALL_STATUSES = {"PASS", "FAIL", "BLOCKED", "PARTIAL"}


class VerificationGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    category: str
    command: str | None
    required: bool = True
    scope: tuple[str, ...] = ()
    skip_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckSpec":
        allowed = {"check_id", "category", "command", "required", "scope", "skip_reason"}
        extra = set(data) - allowed
        if extra:
            raise VerificationGateError(f"unknown check fields: {sorted(extra)}")
        check_id = data.get("check_id")
        category = data.get("category")
        command = data.get("command")
        required = data.get("required", True)
        scope = data.get("scope", [])
        skip_reason = data.get("skip_reason")
        if not isinstance(check_id, str) or not check_id.strip():
            raise VerificationGateError("check_id must be a non-empty string")
        if category not in CATEGORIES:
            raise VerificationGateError(f"invalid verification category: {category!r}")
        if command is not None and (not isinstance(command, str) or not command.strip()):
            raise VerificationGateError("command must be null or a non-empty string")
        if not isinstance(required, bool):
            raise VerificationGateError("required must be boolean")
        if not isinstance(scope, list) or any(not isinstance(v, str) or not v.strip() for v in scope):
            raise VerificationGateError("scope must be a list of non-empty strings")
        if skip_reason is not None and (not isinstance(skip_reason, str) or not skip_reason.strip()):
            raise VerificationGateError("skip_reason must be null or a non-empty string")
        if command is None and skip_reason is None:
            raise VerificationGateError("a check without a command requires skip_reason")
        return cls(
            check_id=check_id.strip(),
            category=category,
            command=command.strip() if isinstance(command, str) else None,
            required=required,
            scope=tuple(v.strip() for v in scope),
            skip_reason=skip_reason.strip() if isinstance(skip_reason, str) else None,
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_full_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(FULL_SHA_RE.fullmatch(value))


def evidence_path(project_root: str | Path, task_id: str) -> Path:
    return task_dir(project_root, task_id) / "verification.jsonl"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def validate_evidence(record: dict[str, Any]) -> None:
    required_fields = {
        "schema_version", "task_id", "candidate_sha", "check_id", "category",
        "required", "status", "started_at", "completed_at", "exit_code",
        "command", "scope", "summary", "reason",
    }
    if set(record) != required_fields:
        raise VerificationGateError("verification evidence has invalid shape")
    if record["schema_version"] != SCHEMA_VERSION:
        raise VerificationGateError("unsupported evidence schema version")
    if not is_full_sha(record["candidate_sha"]):
        raise VerificationGateError("evidence candidate_sha must be a full 40-character SHA")
    if not isinstance(record["check_id"], str) or not record["check_id"]:
        raise VerificationGateError("evidence check_id is required")
    if record["category"] not in CATEGORIES:
        raise VerificationGateError("invalid evidence category")
    if not isinstance(record["required"], bool):
        raise VerificationGateError("evidence required must be boolean")
    if record["status"] not in CHECK_STATUSES:
        raise VerificationGateError("invalid evidence status")
    if not isinstance(record["scope"], list) or any(not isinstance(v, str) for v in record["scope"]):
        raise VerificationGateError("invalid evidence scope")
    if record["exit_code"] is not None and not isinstance(record["exit_code"], int):
        raise VerificationGateError("invalid evidence exit_code")
    if record["command"] is not None and not isinstance(record["command"], str):
        raise VerificationGateError("invalid evidence command")
    if record["status"] in {"FAIL", "BLOCKED", "SKIPPED"} and not record.get("reason"):
        raise VerificationGateError(f"{record['status']} evidence requires reason")


def _concise_output(stdout: str, stderr: str, *, max_chars: int = 1200) -> str:
    text = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    if not text:
        return "command completed with no output"
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 30] + "\n...[output truncated]..."


def run_check(
    spec: CheckSpec,
    *,
    project_root: str | Path,
    task_id: str,
    candidate_sha: str,
    timeout_seconds: int = 900,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not is_full_sha(candidate_sha):
        raise VerificationGateError("candidate_sha must be a full 40-character SHA")
    started = utc_now()
    if spec.command is None:
        record = {
            "schema_version": SCHEMA_VERSION,
            "task_id": task_id,
            "candidate_sha": candidate_sha.lower(),
            "check_id": spec.check_id,
            "category": spec.category,
            "required": spec.required,
            "status": "SKIPPED",
            "started_at": started,
            "completed_at": utc_now(),
            "exit_code": None,
            "command": None,
            "scope": list(spec.scope),
            "summary": "check was not executed",
            "reason": spec.skip_reason or "check skipped",
        }
        validate_evidence(record)
        return record

    try:
        proc = subprocess.run(
            spec.command,
            cwd=str(Path(project_root).resolve()),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
        status = "PASS" if proc.returncode == 0 else "FAIL"
        summary = _concise_output(proc.stdout, proc.stderr)
        reason = None if status == "PASS" else f"command exited with code {proc.returncode}"
        exit_code: int | None = proc.returncode
    except subprocess.TimeoutExpired as exc:
        status = "BLOCKED"
        summary = _concise_output(exc.stdout if isinstance(exc.stdout, str) else "", exc.stderr if isinstance(exc.stderr, str) else "")
        reason = f"command timed out after {timeout_seconds} seconds"
        exit_code = None
    except OSError as exc:
        status = "BLOCKED"
        summary = str(exc)
        reason = f"command could not be started: {exc}"
        exit_code = None

    record = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "candidate_sha": candidate_sha.lower(),
        "check_id": spec.check_id,
        "category": spec.category,
        "required": spec.required,
        "status": status,
        "started_at": started,
        "completed_at": utc_now(),
        "exit_code": exit_code,
        "command": spec.command,
        "scope": list(spec.scope),
        "summary": summary,
        "reason": reason,
    }
    validate_evidence(record)
    return record


def aggregate_status(records: Iterable[dict[str, Any]]) -> str:
    rows = list(records)
    if not rows:
        return "BLOCKED"
    required_rows = [r for r in rows if r["required"]]
    optional_rows = [r for r in rows if not r["required"]]

    if any(r["status"] == "FAIL" for r in required_rows):
        return "FAIL"
    if any(r["status"] == "BLOCKED" for r in required_rows):
        return "BLOCKED"
    if any(r["status"] == "SKIPPED" for r in required_rows):
        return "PARTIAL"
    if required_rows and all(r["status"] == "PASS" for r in required_rows):
        if any(r["status"] in {"FAIL", "BLOCKED", "SKIPPED"} for r in optional_rows):
            return "PARTIAL"
        return "PASS"
    if not required_rows:
        if all(r["status"] == "PASS" for r in optional_rows) and optional_rows:
            return "PASS"
        return "PARTIAL"
    return "PARTIAL"


def default_checks_from_context(context: dict[str, Any], *, complexity_tier: str, risk_level: str) -> list[CheckSpec]:
    commands = context.get("commands") or {}
    checks: list[CheckSpec] = []

    def add(kind: str, category: str, required: bool) -> None:
        values = commands.get(kind) or []
        if values:
            for i, command in enumerate(values, 1):
                checks.append(CheckSpec(f"{kind}-{i}", category, command, required))
        elif required:
            checks.append(CheckSpec(f"{kind}-missing", category, None, True, (), f"required {kind} command is not configured"))

    tier = complexity_tier.upper()
    risk = risk_level.upper()
    add("lint", "LINT", tier in {"STANDARD", "COMPLEX"})
    add("typecheck", "TYPECHECK", tier == "COMPLEX" or risk in {"HIGH", "CRITICAL"})
    add("test", "REGRESSION_TEST" if tier == "COMPLEX" else "FOCUSED_TEST", True)
    add("build", "BUILD", tier in {"STANDARD", "COMPLEX"})
    return checks


def apply_verification_summary(
    state: dict[str, Any],
    *,
    candidate_sha: str,
    records: list[dict[str, Any]],
    overall_status: str | None = None,
) -> dict[str, Any]:
    if not is_full_sha(candidate_sha):
        raise VerificationGateError("candidate_sha must be a full 40-character SHA")
    if any(r["candidate_sha"].lower() != candidate_sha.lower() for r in records):
        raise VerificationGateError("all evidence must be bound to the same candidate SHA")
    status = overall_status or aggregate_status(records)
    if status not in OVERALL_STATUSES:
        raise VerificationGateError(f"invalid overall verification status: {status}")
    if status == "PASS":
        if not records:
            raise VerificationGateError("PASS requires verification evidence")
        if any(r["required"] and r["status"] != "PASS" for r in records):
            raise VerificationGateError("PASS requires every required check to PASS")
        if any((not r["required"]) and r["status"] != "PASS" for r in records):
            raise VerificationGateError("PASS cannot hide non-passing optional evidence; use PARTIAL")

    result = copy.deepcopy(state)
    implementation_sha = (result.get("implementation") or {}).get("candidate_sha")
    if implementation_sha is not None and implementation_sha.lower() != candidate_sha.lower():
        raise VerificationGateError("candidate SHA does not match implementation.candidate_sha")
    result["implementation"]["candidate_sha"] = candidate_sha.lower()
    verification = result["verification"]
    verification["overall_status"] = status
    verification["candidate_sha"] = candidate_sha.lower()
    verification["required_checks"] = [r["check_id"] for r in records if r["required"]]
    verification["completed_checks"] = [r["check_id"] for r in records if r["status"] == "PASS"]
    verification["failed_checks"] = [r["check_id"] for r in records if r["status"] == "FAIL"]
    verification["skipped_checks"] = [r["check_id"] for r in records if r["status"] in {"SKIPPED", "BLOCKED"}]
    validate_task_state(result, expected_task_id=result["identity"]["id"])
    return result


def verify_task(
    project_root: str | Path,
    *,
    candidate_sha: str,
    checks: list[CheckSpec],
    task_id: str | None = None,
    timeout_seconds: int = 900,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not is_full_sha(candidate_sha):
        raise VerificationGateError("candidate_sha must be a full 40-character SHA")
    if not checks:
        raise VerificationGateError("verification requires at least one check")
    ids = [c.check_id for c in checks]
    if len(ids) != len(set(ids)):
        raise VerificationGateError("verification check_id values must be unique")

    try:
        state = load_task(project_root, task_id)
    except TaskStoreError as exc:
        raise VerificationGateError(str(exc)) from exc
    actual_task_id = state["identity"]["id"]
    implementation_sha = (state.get("implementation") or {}).get("candidate_sha")
    if implementation_sha is not None and implementation_sha.lower() != candidate_sha.lower():
        raise VerificationGateError("candidate SHA does not match implementation.candidate_sha")
    records: list[dict[str, Any]] = []
    ledger = evidence_path(project_root, actual_task_id)
    for spec in checks:
        record = run_check(
            spec,
            project_root=project_root,
            task_id=actual_task_id,
            candidate_sha=candidate_sha,
            timeout_seconds=timeout_seconds,
        )
        _append_jsonl(ledger, record)
        records.append(record)

    updated = apply_verification_summary(state, candidate_sha=candidate_sha, records=records)
    save_task(project_root, updated)
    return updated, records


def _load_checks(path: str | Path) -> list[CheckSpec]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VerificationGateError(f"cannot load checks file: {exc}") from exc
    if not isinstance(data, list):
        raise VerificationGateError("checks file must contain a JSON array")
    return [CheckSpec.from_dict(item) if isinstance(item, dict) else (_ for _ in ()).throw(VerificationGateError("each check must be an object")) for item in data]


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the v2 Central Verification Gate")
    ap.add_argument("--root", default=".")
    ap.add_argument("--task-id")
    ap.add_argument("--candidate-sha", required=True)
    ap.add_argument("--checks", required=True, help="JSON file containing verification check specifications")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()
    try:
        checks = _load_checks(args.checks)
        state, records = verify_task(
            args.root,
            task_id=args.task_id,
            candidate_sha=args.candidate_sha,
            checks=checks,
            timeout_seconds=args.timeout,
        )
        print(json.dumps({"verification": state["verification"], "evidence": records}, indent=2, ensure_ascii=False))
    except VerificationGateError as exc:
        raise SystemExit(f"verification gate error: {exc}") from exc


if __name__ == "__main__":
    main()
