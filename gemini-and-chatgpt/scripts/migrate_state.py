#!/usr/bin/env python3
"""Import legacy .ai/review-state.json into authoritative v2 task state.

Migration preserves useful delivery/review identity but deliberately marks all
legacy approval as non-authoritative until GitHub HEAD is reconciled again.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from state_machine import is_full_sha
from task_store import (
    TASK_ID_RE,
    TaskStoreError,
    create_checkpoint,
    create_task,
    generate_task_id,
    save_task,
    set_active_task,
    task_dir,
    utc_now,
)

LEGACY_STATE_MAP = {
    "TASK_RECEIVED": "RECEIVED",
    "PLANNING": "PLANNING",
    "IMPLEMENTING": "IMPLEMENTING",
    "VERIFYING": "VERIFYING",
    "CREATE_OR_UPDATE_PR": "PR_PREPARING",
    "REVIEWING": "REVIEWING",
    "FIXING": "FIXING",
    "RELEASE_GATE": "HUMAN_DECISION",
    "APPROVED": "HUMAN_DECISION",
    "HUMAN_DECISION": "HUMAN_DECISION",
    "FAILED": "FAILED",
}
ALLOWED_VERDICTS = {"APPROVED_TO_MERGE", "REQUEST_CHANGES", "NEEDS_HUMAN_DECISION"}


class MigrationError(RuntimeError):
    pass


def _read_legacy(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MigrationError(f"legacy state not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MigrationError(f"legacy state is corrupt: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise MigrationError("legacy state must be a JSON object")
    return data


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def migrate_legacy_state(
    project_root: str | Path,
    legacy_path: str | Path,
    *,
    original_request: str | None = None,
    normalized_title: str | None = None,
    activate: bool = True,
    timestamp: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    legacy = _read_legacy(Path(legacy_path))
    now = timestamp or utc_now()
    legacy_task_id = str(legacy.get("task_id") or "legacy-task")
    title = normalized_title or f"legacy review {legacy_task_id}"
    request = original_request or f"Resume legacy review task {legacy_task_id}"

    candidate_id = legacy_task_id if TASK_ID_RE.fullmatch(legacy_task_id) else None
    if candidate_id and (task_dir(root, candidate_id) / "state.json").exists():
        raise MigrationError(f"target task already exists: {candidate_id}")
    task_id = candidate_id or generate_task_id(root, title)

    max_rounds = _int(legacy.get("max_review_rounds"), 5)
    max_rounds = min(max(max_rounds, 1), 20)
    state = create_task(
        root,
        request,
        title,
        task_id=task_id,
        max_rounds=max_rounds,
        activate=False,
    )
    state = copy.deepcopy(state)

    mapped = LEGACY_STATE_MAP.get(str(legacy.get("state") or "TASK_RECEIVED"), "HUMAN_DECISION")
    original_mapped = mapped

    head = legacy.get("head_sha")
    full_head = head.lower() if is_full_sha(head) else None
    pr_number = legacy.get("pr_number") if isinstance(legacy.get("pr_number"), int) else None
    pr_url = legacy.get("pr_url") if isinstance(legacy.get("pr_url"), str) else None
    pr_state = legacy.get("pr_state") if legacy.get("pr_state") in {"OPEN", "CLOSED", "MERGED"} else None

    needs_reconcile = bool(pr_number or pr_url or full_head)
    if mapped == "REVIEWING":
        mapped = "BLOCKED"
        state["lifecycle"]["resume_state"] = "REVIEWING"

    state["lifecycle"].update(
        {
            "current_state": mapped,
            "previous_state": None,
            "state_entered_at": now,
            "transition_reason": "migrated from legacy review-state.json",
        }
    )
    if mapped != "BLOCKED":
        state["lifecycle"]["resume_state"] = None

    state["delivery"].update(
        {
            "repository": legacy.get("repository") if isinstance(legacy.get("repository"), str) else None,
            "base_branch": legacy.get("base_branch") if isinstance(legacy.get("base_branch"), str) else None,
            "head_branch": legacy.get("head_branch") if isinstance(legacy.get("head_branch"), str) else None,
            "pr_number": pr_number,
            "pr_url": pr_url,
            "pr_state": pr_state,
            "head_sha": full_head,
            "last_push_at": None,
        }
    )

    round_no = _int(legacy.get("review_round"), 0)
    round_no = min(max(round_no, 0), max_rounds)
    verdict = legacy.get("review") if legacy.get("review") in ALLOWED_VERDICTS else None
    state["review"].update(
        {
            "round": round_no,
            "max_rounds": max_rounds,
            "current_target_sha": full_head,
            "current_verdict": verdict,
            "approval_valid": False,
        }
    )

    ci = legacy.get("ci")
    if ci is not None:
        state["verification"]["overall_status"] = "PARTIAL"
        state["verification"]["skipped_checks"].append(
            "legacy verification/CI result is not bound to v2 candidate evidence"
        )

    state["decisions"].append(
        {
            "type": "LEGACY_STATE_MIGRATION",
            "legacy_task_id": legacy_task_id,
            "legacy_state": legacy.get("state"),
            "mapped_state": original_mapped,
            "recorded_at": now,
        }
    )
    if needs_reconcile:
        state["blockers"].append(
            {
                "type": "GITHUB_IDENTITY_RECONCILIATION_REQUIRED",
                "message": "Migrated PR/HEAD metadata is non-authoritative until Git/GitHub state is recomputed.",
                "recorded_at": now,
            }
        )

    if original_mapped in {"RELEASE_GATE", "APPROVED"} or legacy.get("state") in {"RELEASE_GATE", "APPROVED"}:
        state["release"]["human_required"] = True
        state["release"]["human_reason"] = "legacy approval cannot be trusted without exact current HEAD reconciliation"
        state["release"]["status"] = "HUMAN_DECISION"
        state["release"]["approved_sha"] = None

    save_task(root, state, timestamp=now)
    cp_path, state = create_checkpoint(
        root,
        state,
        reason="RECOVERY",
        resume_hint=("reconcile GitHub identity, then resume REVIEWING" if mapped == "BLOCKED" else None),
        timestamp=now,
        update_state=False,
    )
    save_task(root, state, timestamp=now)
    history = task_dir(root, task_id) / "transition-history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "from": "LEGACY",
            "to": mapped,
            "timestamp": now,
            "reason": "imported legacy review-state.json",
            "actor": "ORCHESTRATOR",
            "checkpoint": cp_path.relative_to(root).as_posix(),
        }, sort_keys=True) + "\n")
    if activate:
        set_active_task(root, task_id, timestamp=now)
    return state


def main() -> None:
    ap = argparse.ArgumentParser(description="Migrate legacy .ai/review-state.json to v2 task state")
    ap.add_argument("--root", default=".")
    ap.add_argument("--legacy", default=".ai/review-state.json")
    ap.add_argument("--request")
    ap.add_argument("--title")
    ap.add_argument("--no-activate", action="store_true")
    args = ap.parse_args()
    legacy = Path(args.legacy)
    if not legacy.is_absolute():
        legacy = Path(args.root).resolve() / legacy
    try:
        state = migrate_legacy_state(
            args.root,
            legacy,
            original_request=args.request,
            normalized_title=args.title,
            activate=not args.no_activate,
        )
    except (MigrationError, TaskStoreError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        raise SystemExit(2)
    print(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
