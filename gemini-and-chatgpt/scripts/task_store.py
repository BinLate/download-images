#!/usr/bin/env python3
"""Authoritative v2 task-state storage, checkpoints, and transition history."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from state_machine import STATES, StateTransitionError, is_full_sha, transition_state

SCHEMA_VERSION = "2.0.0"
TASK_ID_RE = re.compile(r"^T-[0-9]{8}-[0-9]{3}-[a-z0-9][a-z0-9-]*$")
TOP_LEVEL_KEYS = {
    "schema_version",
    "identity",
    "classification",
    "requirements",
    "plan",
    "roles",
    "lifecycle",
    "implementation",
    "verification",
    "delivery",
    "review",
    "decisions",
    "blockers",
    "release",
    "checkpoint",
}


class TaskStoreError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(project_root: str | Path) -> Path:
    return Path(project_root).resolve()


def ai_dir(project_root: str | Path) -> Path:
    return _root(project_root) / ".ai"


def tasks_dir(project_root: str | Path) -> Path:
    return ai_dir(project_root) / "tasks"


def task_dir(project_root: str | Path, task_id: str) -> Path:
    if not TASK_ID_RE.fullmatch(task_id):
        raise TaskStoreError(f"invalid v2 task id: {task_id!r}")
    return tasks_dir(project_root) / task_id


def state_path(project_root: str | Path, task_id: str) -> Path:
    return task_dir(project_root, task_id) / "state.json"


def active_task_path(project_root: str | Path) -> Path:
    return ai_dir(project_root) / "active-task.json"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TaskStoreError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TaskStoreError(f"corrupt JSON; refusing unsafe reset: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TaskStoreError(f"expected JSON object: {path}")
    return data


def _require_dict(state: dict[str, Any], key: str) -> dict[str, Any]:
    value = state.get(key)
    if not isinstance(value, dict):
        raise TaskStoreError(f"task state field {key!r} must be an object")
    return value


def validate_task_state(state: dict[str, Any], *, expected_task_id: str | None = None) -> None:
    if set(state) != TOP_LEVEL_KEYS:
        missing = sorted(TOP_LEVEL_KEYS - set(state))
        extra = sorted(set(state) - TOP_LEVEL_KEYS)
        raise TaskStoreError(f"invalid task-state shape; missing={missing} extra={extra}")
    if state.get("schema_version") != SCHEMA_VERSION:
        raise TaskStoreError(f"unsupported task-state schema version: {state.get('schema_version')!r}")

    identity = _require_dict(state, "identity")
    task_id = identity.get("id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise TaskStoreError(f"invalid task identity: {task_id!r}")
    if expected_task_id and task_id != expected_task_id:
        raise TaskStoreError(f"task identity mismatch: expected {expected_task_id}, found {task_id}")
    for key in ("original_request", "normalized_title", "created_at", "updated_at"):
        if not isinstance(identity.get(key), str) or not identity[key]:
            raise TaskStoreError(f"identity.{key} must be a non-empty string")

    classification = _require_dict(state, "classification")
    if classification.get("complexity_tier") not in {"UNCLASSIFIED", "SIMPLE", "STANDARD", "COMPLEX"}:
        raise TaskStoreError("invalid classification.complexity_tier")
    if classification.get("risk_level") not in {"UNKNOWN", "LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        raise TaskStoreError("invalid classification.risk_level")

    lifecycle = _require_dict(state, "lifecycle")
    if lifecycle.get("current_state") not in STATES:
        raise TaskStoreError("invalid lifecycle.current_state")
    if lifecycle.get("previous_state") is not None and lifecycle.get("previous_state") not in STATES:
        raise TaskStoreError("invalid lifecycle.previous_state")
    if lifecycle.get("resume_state") is not None and lifecycle.get("resume_state") not in STATES:
        raise TaskStoreError("invalid lifecycle.resume_state")

    review = _require_dict(state, "review")
    try:
        current = int(review.get("round"))
        maximum = int(review.get("max_rounds"))
    except (TypeError, ValueError) as exc:
        raise TaskStoreError("review round values must be integers") from exc
    if maximum < 1 or maximum > 20 or current < 0 or current > maximum:
        raise TaskStoreError(f"invalid review round bounds: {current}/{maximum}")

    for parent, key in (
        ("implementation", "candidate_sha"),
        ("verification", "candidate_sha"),
        ("delivery", "head_sha"),
        ("review", "current_target_sha"),
        ("release", "approved_sha"),
    ):
        value = _require_dict(state, parent).get(key)
        if value is not None and not is_full_sha(value):
            raise TaskStoreError(f"{parent}.{key} must be null or a full 40-character SHA")

    if not isinstance(state.get("decisions"), list) or not isinstance(state.get("blockers"), list):
        raise TaskStoreError("decisions and blockers must be arrays")


def _slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return (slug[:48].rstrip("-") or "task")


def generate_task_id(project_root: str | Path, title: str, *, now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    day = dt.strftime("%Y%m%d")
    base = tasks_dir(project_root)
    maximum = 0
    if base.exists():
        prefix = f"T-{day}-"
        for child in base.iterdir():
            if not child.is_dir() or not child.name.startswith(prefix):
                continue
            match = re.match(rf"^T-{day}-([0-9]{{3}})-", child.name)
            if match:
                maximum = max(maximum, int(match.group(1)))
    sequence = maximum + 1
    if sequence > 999:
        raise TaskStoreError(f"daily task id sequence exhausted for {day}")
    return f"T-{day}-{sequence:03d}-{_slugify(title)}"


def new_task_state(
    task_id: str,
    original_request: str,
    normalized_title: str,
    *,
    max_rounds: int = 5,
    timestamp: str | None = None,
) -> dict[str, Any]:
    if not TASK_ID_RE.fullmatch(task_id):
        raise TaskStoreError(f"invalid v2 task id: {task_id!r}")
    if not original_request.strip() or not normalized_title.strip():
        raise TaskStoreError("task request and title must be non-empty")
    if max_rounds < 1 or max_rounds > 20:
        raise TaskStoreError("max_rounds must be between 1 and 20")
    now = timestamp or utc_now()
    base = f".ai/tasks/{task_id}"
    state = {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "id": task_id,
            "original_request": original_request.strip(),
            "normalized_title": normalized_title.strip(),
            "created_at": now,
            "updated_at": now,
        },
        "classification": {
            "kind": "UNKNOWN",
            "complexity_tier": "UNCLASSIFIED",
            "risk_level": "UNKNOWN",
            "score": 0,
            "signals": [],
            "architect_required": False,
            "planner_required": False,
            "human_precheck_required": False,
        },
        "requirements": {
            "goal": original_request.strip(),
            "in_scope": [],
            "out_of_scope": [],
            "constraints": [],
            "acceptance_criteria": [],
            "release_constraints": [],
            "assumptions": [],
        },
        "plan": {
            "required": False,
            "status": "NOT_REQUIRED",
            "plan_path": None,
            "work_item_count": 0,
            "completed_count": 0,
            "current_work_item": None,
            "current_work_items": [],
        },
        "roles": {"active": ["ORCHESTRATOR"], "completed": []},
        "lifecycle": {
            "current_state": "RECEIVED",
            "previous_state": None,
            "state_entered_at": now,
            "transition_reason": "task initialized",
            "resume_state": None,
            "local_repair_attempts": 0,
        },
        "implementation": {
            "branch": None,
            "candidate_sha": None,
            "changed_files": [],
            "work_items_completed": [],
            "work_items_remaining": [],
        },
        "verification": {
            "overall_status": "NOT_RUN",
            "candidate_sha": None,
            "required_checks": [],
            "completed_checks": [],
            "failed_checks": [],
            "skipped_checks": [],
            "evidence_ledger_path": f"{base}/verification.jsonl",
        },
        "delivery": {
            "repository": None,
            "base_branch": None,
            "head_branch": None,
            "pr_number": None,
            "pr_url": None,
            "pr_state": None,
            "head_sha": None,
            "last_push_at": None,
        },
        "review": {
            "round": 0,
            "max_rounds": max_rounds,
            "current_target_sha": None,
            "current_verdict": None,
            "current_findings": [],
            "history_path": f"{base}/review-history.jsonl",
            "approval_valid": False,
        },
        "decisions": [],
        "blockers": [],
        "release": {
            "status": "PENDING",
            "merge_policy": "human_only",
            "human_required": False,
            "human_reason": None,
            "approved_sha": None,
        },
        "checkpoint": {"latest_path": None, "latest_at": None},
    }
    validate_task_state(state, expected_task_id=task_id)
    return state


def set_active_task(project_root: str | Path, task_id: str, *, timestamp: str | None = None) -> Path:
    path = state_path(project_root, task_id)
    if not path.exists():
        raise TaskStoreError(f"cannot activate missing task: {task_id}")
    payload = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "state_path": f".ai/tasks/{task_id}/state.json",
        "updated_at": timestamp or utc_now(),
    }
    target = active_task_path(project_root)
    _write_json(target, payload)
    return target


def get_active_task_id(project_root: str | Path) -> str:
    data = _read_json(active_task_path(project_root))
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        raise TaskStoreError("active-task.json contains an invalid task id")
    return task_id


def save_task(project_root: str | Path, state: dict[str, Any], *, timestamp: str | None = None) -> Path:
    task_id = (state.get("identity") or {}).get("id")
    if not isinstance(task_id, str):
        raise TaskStoreError("task state identity.id is missing")
    now = timestamp or utc_now()
    state = copy.deepcopy(state)
    state["identity"]["updated_at"] = now
    validate_task_state(state, expected_task_id=task_id)
    path = state_path(project_root, task_id)
    _write_json(path, state)
    return path


def create_task(
    project_root: str | Path,
    original_request: str,
    normalized_title: str,
    *,
    task_id: str | None = None,
    max_rounds: int = 5,
    activate: bool = True,
    now: datetime | None = None,
) -> dict[str, Any]:
    dt = now or datetime.now(timezone.utc)
    timestamp = dt.isoformat()
    task_id = task_id or generate_task_id(project_root, normalized_title, now=dt)
    path = state_path(project_root, task_id)
    if path.exists():
        raise TaskStoreError(f"task already exists: {task_id}")
    state = new_task_state(task_id, original_request, normalized_title, max_rounds=max_rounds, timestamp=timestamp)
    save_task(project_root, state, timestamp=timestamp)
    if activate:
        set_active_task(project_root, task_id, timestamp=timestamp)
    return state


def migrate_state(state: dict[str, Any]) -> dict[str, Any]:
    """Transparently upgrade older schema tasks to the current schema."""
    migrated = copy.deepcopy(state)
    
    # Pre-C4 migration: missing current_work_items
    if "plan" in migrated and isinstance(migrated["plan"], dict):
        if "current_work_items" not in migrated["plan"]:
            cw = migrated["plan"].get("current_work_item")
            migrated["plan"]["current_work_items"] = [cw] if cw else []
            
    # Always bump to current schema if we migrated
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated


def load_task(project_root: str | Path, task_id: str | None = None) -> dict[str, Any]:
    resolved = task_id or get_active_task_id(project_root)
    data = _read_json(state_path(project_root, resolved))
    
    # Run schema migration hook
    if data.get("schema_version") != SCHEMA_VERSION or (
        "plan" in data and "current_work_items" not in data["plan"]
    ):
        data = migrate_state(data)
        
    validate_task_state(data, expected_task_id=resolved)
    return data


def _checkpoint_summary(state: dict[str, Any], reason: str, resume_hint: str | None, timestamp: str) -> dict[str, Any]:
    lifecycle = state["lifecycle"]
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": state["identity"]["id"],
        "created_at": timestamp,
        "reason": reason,
        "lifecycle": {
            "current_state": lifecycle["current_state"],
            "previous_state": lifecycle["previous_state"],
            "resume_state": lifecycle["resume_state"],
        },
        "implementation": {
            "branch": state["implementation"]["branch"],
            "candidate_sha": state["implementation"]["candidate_sha"],
            "changed_files": list(state["implementation"]["changed_files"]),
        },
        "verification": {
            "overall_status": state["verification"]["overall_status"],
            "candidate_sha": state["verification"]["candidate_sha"],
            "evidence_ledger_path": state["verification"]["evidence_ledger_path"],
        },
        "delivery": {
            "pr_number": state["delivery"]["pr_number"],
            "pr_url": state["delivery"]["pr_url"],
            "head_sha": state["delivery"]["head_sha"],
        },
        "review": {
            "round": state["review"]["round"],
            "max_rounds": state["review"]["max_rounds"],
            "current_target_sha": state["review"]["current_target_sha"],
            "current_verdict": state["review"]["current_verdict"],
            "approval_valid": state["review"]["approval_valid"],
        },
        "blockers": copy.deepcopy(state["blockers"]),
        "resume_hint": resume_hint,
    }


def create_checkpoint(
    project_root: str | Path,
    state: dict[str, Any],
    *,
    reason: str = "MANUAL",
    resume_hint: str | None = None,
    timestamp: str | None = None,
    update_state: bool = True,
) -> tuple[Path, dict[str, Any]]:
    allowed_reasons = {"STATE_TRANSITION", "BLOCKED", "HUMAN_GATE", "RECOVERY", "MANUAL"}
    if reason not in allowed_reasons:
        raise TaskStoreError(f"invalid checkpoint reason: {reason}")
    validate_task_state(state)
    now = timestamp or utc_now()
    task_id = state["identity"]["id"]
    compact = now.replace("-", "").replace(":", "").replace("+00:00", "Z").replace(".", "")
    filename = f"{compact}-{state['lifecycle']['current_state']}.json"
    path = task_dir(project_root, task_id) / "checkpoints" / filename
    payload = _checkpoint_summary(state, reason, resume_hint, now)
    _write_json(path, payload)

    updated = copy.deepcopy(state)
    relative = path.relative_to(_root(project_root)).as_posix()
    updated["checkpoint"] = {"latest_path": relative, "latest_at": now}
    if update_state:
        save_task(project_root, updated, timestamp=now)
        
    cleanup_checkpoints(project_root, task_id)
        
    return path, updated


def transition_task(
    project_root: str | Path,
    target: str,
    reason: str,
    *,
    task_id: str | None = None,
    actor: str = "ORCHESTRATOR",
    human_authorized: bool = False,
    timestamp: str | None = None,
) -> dict[str, Any]:
    state = load_task(project_root, task_id)
    now = timestamp or utc_now()
    try:
        transitioned, record = transition_state(
            state,
            target,
            reason,
            actor=actor,
            human_authorized=human_authorized,
            now=now,
        )
    except StateTransitionError as exc:
        raise TaskStoreError(str(exc)) from exc

    cp_reason = "STATE_TRANSITION"
    if target == "BLOCKED":
        cp_reason = "BLOCKED"
    elif target == "HUMAN_DECISION":
        cp_reason = "HUMAN_GATE"

    _, transitioned = create_checkpoint(
        project_root,
        transitioned,
        reason=cp_reason,
        resume_hint=f"resume to {transitioned['lifecycle'].get('resume_state')}" if target in {"BLOCKED", "HUMAN_DECISION"} else None,
        timestamp=now,
        update_state=False,
    )
    save_task(project_root, transitioned, timestamp=now)
    history_path = task_dir(project_root, transitioned["identity"]["id"]) / "transition-history.jsonl"
    _append_jsonl(history_path, record)
    return transitioned


def restore_checkpoint(
    project_root: str | Path,
    checkpoint: str | Path,
    *,
    task_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    state = load_task(project_root, task_id)
    cp_path = Path(checkpoint)
    if not cp_path.is_absolute():
        cp_path = _root(project_root) / cp_path
    payload = _read_json(cp_path)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise TaskStoreError("unsupported checkpoint schema version")
    if payload.get("task_id") != state["identity"]["id"]:
        raise TaskStoreError("checkpoint belongs to a different task")

    restored = copy.deepcopy(state)
    lifecycle = payload.get("lifecycle") or {}
    for key in ("current_state", "previous_state", "resume_state"):
        restored["lifecycle"][key] = lifecycle.get(key)
    restored["lifecycle"]["state_entered_at"] = payload.get("created_at") or restored["lifecycle"]["state_entered_at"]
    restored["lifecycle"]["transition_reason"] = "restored from checkpoint"

    restored["implementation"].update(payload.get("implementation") or {})
    restored["verification"].update(payload.get("verification") or {})
    restored["delivery"].update(payload.get("delivery") or {})
    restored["review"].update(payload.get("review") or {})
    restored["blockers"] = copy.deepcopy(payload.get("blockers") or [])

    now = timestamp or utc_now()
    relative = cp_path.resolve().relative_to(_root(project_root)).as_posix()
    restored["checkpoint"] = {"latest_path": relative, "latest_at": payload.get("created_at")}
    save_task(project_root, restored, timestamp=now)
    _append_jsonl(
        task_dir(project_root, restored["identity"]["id"]) / "transition-history.jsonl",
        {
            "from": state["lifecycle"]["current_state"],
            "to": restored["lifecycle"]["current_state"],
            "timestamp": now,
            "reason": f"restored checkpoint {relative}",
            "actor": "ORCHESTRATOR",
            "recovery": True,
        },
    )
    return restored


def record_delivery_head(
    state: dict[str, Any],
    head_sha: str,
    *,
    timestamp: str | None = None,
    pr_number: int | None = None,
    pr_url: str | None = None,
    pr_state: str | None = None,
    repository: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
) -> dict[str, Any]:
    """Return a copy with refreshed delivery identity and stale approval invalidated."""
    if not is_full_sha(head_sha):
        raise TaskStoreError("delivery HEAD must be a full 40-character SHA")
    result = copy.deepcopy(state)
    delivery = result["delivery"]
    old_head = delivery.get("head_sha")
    delivery["head_sha"] = head_sha.lower()
    delivery["last_push_at"] = timestamp or utc_now()
    if pr_number is not None:
        delivery["pr_number"] = pr_number
    if pr_url is not None:
        delivery["pr_url"] = pr_url
    if pr_state is not None:
        delivery["pr_state"] = pr_state
    if repository is not None:
        delivery["repository"] = repository
    if base_branch is not None:
        delivery["base_branch"] = base_branch
    if head_branch is not None:
        delivery["head_branch"] = head_branch

    if old_head is None or old_head.lower() != head_sha.lower():
        result["review"]["approval_valid"] = False
        result["review"]["current_verdict"] = None
        result["review"]["current_target_sha"] = head_sha.lower()
        result["release"]["approved_sha"] = None
        if result["release"]["status"] == "APPROVED":
            result["release"]["status"] = "PENDING"
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Manage authoritative gemini-and-chatgpt v2 task state")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init")
    p.add_argument("--root", default=".")
    p.add_argument("--request", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--task-id")
    p.add_argument("--max-rounds", type=int, default=5)

    p = sp.add_parser("show")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")

    p = sp.add_parser("transition")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--to", choices=STATES, required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--actor", default="ORCHESTRATOR")
    p.add_argument("--human-authorized", action="store_true")

    p = sp.add_parser("checkpoint")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--reason", default="MANUAL")
    p.add_argument("--resume-hint")

    p = sp.add_parser("restore")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--checkpoint", required=True)

    args = ap.parse_args()
    try:
        if args.cmd == "init":
            data = create_task(
                args.root,
                args.request,
                args.title,
                task_id=args.task_id,
                max_rounds=args.max_rounds,
            )
            print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        elif args.cmd == "show":
            print(json.dumps(load_task(args.root, args.task_id), indent=2, sort_keys=True, ensure_ascii=False))
        elif args.cmd == "transition":
            data = transition_task(
                args.root,
                args.to,
                args.reason,
                task_id=args.task_id,
                actor=args.actor,
                human_authorized=args.human_authorized,
            )
            print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        elif args.cmd == "checkpoint":
            state = load_task(args.root, args.task_id)
            path, updated = create_checkpoint(
                args.root,
                state,
                reason=args.reason,
                resume_hint=args.resume_hint,
            )
            print(json.dumps({"checkpoint": str(path), "state": updated}, indent=2, sort_keys=True, ensure_ascii=False))
        elif args.cmd == "restore":
            data = restore_checkpoint(args.root, args.checkpoint, task_id=args.task_id)
            print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
    except (TaskStoreError, StateTransitionError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

def cleanup_checkpoints(project_root: str | Path, task_id: str, keep: int = 5) -> int:
    base = task_dir(project_root, task_id) / "checkpoints"
    if not base.is_dir():
        return 0
    checkpoints = []
    for child in base.iterdir():
        if child.is_file() and child.name.endswith(".json"):
            checkpoints.append(child)
    checkpoints.sort(key=lambda p: p.name)
    removed = 0
    if len(checkpoints) > keep:
        for p in checkpoints[:-keep]:
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
    return removed

def archive_completed_tasks(project_root: str | Path) -> int:
    base = tasks_dir(project_root)
    archive_dir = base / "archive"
    if not base.is_dir():
        return 0
    now = utc_now()
    now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
    archived_count = 0
    for child in base.iterdir():
        if not child.is_dir() or not TASK_ID_RE.fullmatch(child.name):
            continue
        try:
            state = load_task(project_root, child.name)
            current_state = state["lifecycle"]["current_state"]
            if current_state in {"APPROVED", "ABORTED", "FAILED", "REVIEW_LIMIT_REACHED"}:
                updated_at = state["identity"].get("updated_at")
                if updated_at:
                    up_dt = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    if (now_dt - up_dt).days >= 7:
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        import shutil
                        shutil.move(str(child), str(archive_dir / child.name))
                        archived_count += 1
        except (TaskStoreError, OSError):
            continue
    return archived_count
