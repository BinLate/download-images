#!/usr/bin/env python3
"""MVP-1 v2 orchestrator integration layer.

This module connects classification, planning, verification, delivery identity,
and the existing review loop without replacing GitHub/ChatGPT helpers. It owns
lifecycle routing and review-round progression; storage remains in task_store.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

from plan_store import PlanStoreError, load_plan
from architect_store import ArchitectError, load_architecture
from state_machine import is_full_sha
from task_classifier import apply_classification, classify_task
from action_log import action_log_path, append_action, format_command
from task_store import (
    TaskStoreError,
    create_checkpoint,
    create_task,
    load_task,
    record_delivery_head,
    save_task,
    task_dir,
    transition_task,
)
from verification_gate import CheckSpec, VerificationGateError, verify_task
from context_store import ContextStoreError, load_context, save_context
from project_context_scan import ProjectScanError, freshness as context_freshness, scan_project, slice_context

VERDICTS = {"APPROVED_TO_MERGE", "REQUEST_CHANGES", "NEEDS_HUMAN_DECISION"}


class OrchestratorError(RuntimeError):
    pass


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()


def ensure_project_context(project_root: str | Path, *, refresh_if_stale: bool = True) -> dict[str, Any]:
    """Ensure C2 Project Context exists and is fresh without trusting stale discovery."""
    try:
        context = load_context(project_root)
        status = context_freshness(project_root, context)
        if status["status"] == "FRESH":
            return {"status": "FRESH", "fingerprint": context["discovery"]["fingerprint"], "refreshed": False}
        if not refresh_if_stale:
            raise OrchestratorError(f"project context is STALE: {status['reasons']}")
    except ContextStoreError:
        if not refresh_if_stale:
            raise OrchestratorError("project context is missing")
    context = scan_project(project_root)
    save_context(project_root, context, timestamp=context["updated_at"])
    return {"status": "FRESH", "fingerprint": context["discovery"]["fingerprint"], "refreshed": True}


def initialize_task(
    project_root: str | Path,
    request: str,
    title: str,
    *,
    task_id: str | None = None,
    max_rounds: int = 5,
) -> dict[str, Any]:
    try:
        state = create_task(project_root, request, title, task_id=task_id, max_rounds=max_rounds)
        _, state = create_checkpoint(project_root, state, reason="MANUAL", resume_hint="classify task")
        return state
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def start_task(
    project_root: str | Path,
    request: str,
    title: str,
    *,
    task_id: str | None = None,
    max_rounds: int = 5,
    estimated_files: int | None = None,
    estimated_components: int | None = None,
    explicit_kind: str | None = None,
    ambiguity: bool = False,
) -> dict[str, Any]:
    """Initialize + classify/route in one normal-path command.

    This removes the old init -> classify round trip. Scope estimates must describe
    only the user's candidate-code change, not GitHub/ChatGPT/workflow machinery.
    """
    state = initialize_task(project_root, request, title, task_id=task_id, max_rounds=max_rounds)
    return classify_and_route(
        project_root,
        task_id=state["identity"]["id"],
        estimated_files=estimated_files,
        estimated_components=estimated_components,
        explicit_kind=explicit_kind,
        ambiguity=ambiguity,
    )


def classify_and_route(
    project_root: str | Path,
    *,
    task_id: str | None = None,
    estimated_files: int | None = None,
    estimated_components: int | None = None,
    explicit_kind: str | None = None,
    ambiguity: bool = False,
) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "RECEIVED":
            raise OrchestratorError("classification may run only from RECEIVED")
        c = classify_task(
            state["identity"]["original_request"],
            estimated_files=estimated_files,
            estimated_components=estimated_components,
            explicit_kind=explicit_kind,
            ambiguity=ambiguity,
        )
        state = apply_classification(state, c)
        save_task(project_root, state)
        state = transition_task(project_root, "CLASSIFIED", "task classification resolved", task_id=state["identity"]["id"])
        # C2 keeps discovery proportional: SIMPLE work skips repository scanning;
        # planned or architectural work gets fresh durable context before Planner/Architect.
        if state["classification"]["planner_required"] or state["classification"]["architect_required"]:
            ensure_project_context(project_root, refresh_if_stale=True)
        if state["classification"]["human_precheck_required"]:
            return transition_task(project_root, "HUMAN_DECISION", "risk router requires human precheck", task_id=state["identity"]["id"])
        if state["classification"]["complexity_tier"] == "SIMPLE":
            return transition_task(project_root, "IMPLEMENTING", "simple task bypasses full planner", task_id=state["identity"]["id"])
        return transition_task(project_root, "PLANNING", "planner required by task classification", task_id=state["identity"]["id"])
    except (TaskStoreError, ValueError) as exc:
        raise OrchestratorError(str(exc)) from exc


def mark_plan_ready(project_root: str | Path, *, task_id: str | None = None) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "PLANNING":
            raise OrchestratorError("plan can become ready only from PLANNING")
        plan = load_plan(project_root, state["identity"]["id"])
        if not plan.get("acceptance_criteria"):
            raise OrchestratorError("plan requires acceptance criteria before PLAN_READY")
        state = transition_task(project_root, "PLAN_READY", "durable plan graph is ready", task_id=state["identity"]["id"])
        if state["classification"].get("architect_required"):
            updated = copy.deepcopy(state)
            if "ARCHITECT" not in updated["roles"].setdefault("active", []): updated["roles"]["active"].append("ARCHITECT")
            save_task(project_root, updated)
            return load_task(project_root, state["identity"]["id"])
        return state
    except (TaskStoreError, PlanStoreError) as exc:
        raise OrchestratorError(str(exc)) from exc


def mark_architecture_ready(project_root: str | Path, *, task_id: str | None = None) -> dict[str, Any]:
    """Validate the durable Architect decision and mark the role complete."""
    try:
        state = load_task(project_root, task_id)
        if not state["classification"].get("architect_required"):
            raise OrchestratorError("Architect is not required for this task")
        if state["lifecycle"]["current_state"] != "PLAN_READY":
            raise OrchestratorError("architecture may become ready only from PLAN_READY")
        artifact = load_architecture(project_root, state["identity"]["id"])
        if artifact.get("human_precheck_required"):
            return transition_task(project_root, "HUMAN_DECISION", "Architect decision requires human precheck", task_id=state["identity"]["id"])
        updated = copy.deepcopy(state)
        active = updated["roles"].setdefault("active", [])
        completed = updated["roles"].setdefault("completed", [])
        if "ARCHITECT" in active: active.remove("ARCHITECT")
        if "ARCHITECT" not in completed: completed.append("ARCHITECT")
        updated["decisions"].append({"type":"ARCHITECTURE_READY","artifact":f".ai/tasks/{state['identity']['id']}/architecture.json"})
        save_task(project_root, updated)
        return load_task(project_root, state["identity"]["id"])
    except (TaskStoreError, ArchitectError) as exc:
        raise OrchestratorError(str(exc)) from exc


def begin_implementation(project_root: str | Path, *, task_id: str | None = None) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] == "IMPLEMENTING":
            return state
        if state["classification"].get("architect_required") and "ARCHITECT" not in state["roles"].get("completed", []):
            raise OrchestratorError("Architect decision must be READY before implementation")
        return transition_task(project_root, "IMPLEMENTING", "implementation started", task_id=state["identity"]["id"])
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def begin_verification(
    project_root: str | Path,
    candidate_sha: str,
    *,
    task_id: str | None = None,
    branch: str | None = None,
    changed_files: list[str] | None = None,
) -> dict[str, Any]:
    if not is_full_sha(candidate_sha):
        raise OrchestratorError("candidate_sha must be a full 40-character SHA")
    try:
        state = load_task(project_root, task_id)
        current = state["lifecycle"]["current_state"]
        if current not in {"IMPLEMENTING", "FIXING"}:
            raise OrchestratorError("verification may begin only after IMPLEMENTING or FIXING")
        updated = copy.deepcopy(state)
        old_candidate = updated["implementation"].get("candidate_sha")
        updated["implementation"]["candidate_sha"] = candidate_sha.lower()
        if branch is not None:
            updated["implementation"]["branch"] = branch
        if changed_files is not None:
            updated["implementation"]["changed_files"] = list(dict.fromkeys(changed_files))
        if old_candidate is None or old_candidate.lower() != candidate_sha.lower():
            updated["verification"].update({
                "overall_status": "NOT_RUN",
                "candidate_sha": None,
                "required_checks": [],
                "completed_checks": [],
                "failed_checks": [],
                "skipped_checks": [],
            })
        save_task(project_root, updated)
        return transition_task(project_root, "VERIFYING", "candidate commit ready for verification", task_id=updated["identity"]["id"])
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def run_verification(
    project_root: str | Path,
    candidate_sha: str,
    checks: list[CheckSpec],
    *,
    task_id: str | None = None,
    timeout_seconds: int = 900,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "VERIFYING":
            raise OrchestratorError("Central Verification Gate may run only in VERIFYING")
        state, records = verify_task(
            project_root,
            candidate_sha=candidate_sha,
            checks=checks,
            task_id=state["identity"]["id"],
            timeout_seconds=timeout_seconds,
        )
        if state["verification"]["overall_status"] == "PASS":
            state = transition_task(project_root, "PR_PREPARING", "Central Verification Gate passed", task_id=state["identity"]["id"])
        return state, records
    except (TaskStoreError, VerificationGateError) as exc:
        raise OrchestratorError(str(exc)) from exc


def verify_candidate(
    project_root: str | Path,
    candidate_sha: str,
    checks: list[CheckSpec],
    *,
    task_id: str | None = None,
    branch: str | None = None,
    changed_files: list[str] | None = None,
    timeout_seconds: int = 900,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Bind a candidate and run the Central Verification Gate in one normal-path call."""
    state = load_task(project_root, task_id)
    current = state["lifecycle"]["current_state"]
    if current in {"IMPLEMENTING", "FIXING"}:
        state = begin_verification(
            project_root,
            candidate_sha,
            task_id=state["identity"]["id"],
            branch=branch,
            changed_files=changed_files,
        )
    elif current != "VERIFYING":
        raise OrchestratorError(f"candidate verification requires IMPLEMENTING, FIXING, or VERIFYING; current state is {current}")
    return run_verification(
        project_root,
        candidate_sha,
        checks,
        task_id=state["identity"]["id"],
        timeout_seconds=timeout_seconds,
    )


def sync_delivery(
    project_root: str | Path,
    *,
    head_sha: str,
    pr_number: int,
    pr_url: str,
    pr_state: str,
    repository: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "PR_PREPARING":
            raise OrchestratorError("delivery identity may be synchronized only in PR_PREPARING")
        candidate = state["verification"].get("candidate_sha")
        if not is_full_sha(candidate) or candidate.lower() != head_sha.lower():
            raise OrchestratorError("PR HEAD must exactly match the verified candidate SHA")
        state = record_delivery_head(
            state,
            head_sha,
            pr_number=pr_number,
            pr_url=pr_url,
            pr_state=pr_state,
            repository=repository,
            base_branch=base_branch,
            head_branch=head_branch,
        )
        save_task(project_root, state)
        return state
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def enter_review(project_root: str | Path, *, task_id: str | None = None) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "PR_PREPARING":
            raise OrchestratorError("review may begin only from PR_PREPARING")
        head = state["delivery"].get("head_sha")
        if not is_full_sha(head):
            raise OrchestratorError("review requires exact PR HEAD")
        current = int(state["review"].get("round", 0))
        maximum = int(state["review"].get("max_rounds", 5))
        if current >= maximum:
            raise OrchestratorError(f"review round limit reached ({current}/{maximum})")
        updated = copy.deepcopy(state)
        updated["review"]["current_verdict"] = None
        updated["review"]["current_findings"] = []
        updated["review"]["approval_valid"] = False
        save_task(project_root, updated)
        # state_machine.py owns the actual review-round increment and target-SHA bind.
        return transition_task(project_root, "REVIEWING", f"starting independent review round {current + 1}", task_id=updated["identity"]["id"])
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def record_review_verdict(
    project_root: str | Path,
    verdict: str,
    target_sha: str,
    *,
    findings: list[dict[str, Any]] | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    verdict = verdict.upper()
    if verdict not in VERDICTS:
        raise OrchestratorError(f"unsupported review verdict: {verdict}")
    if not is_full_sha(target_sha):
        raise OrchestratorError("review target SHA must be a full 40-character SHA")
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "REVIEWING":
            raise OrchestratorError("review verdict may be recorded only in REVIEWING")
        head = state["delivery"].get("head_sha")
        expected = state["review"].get("current_target_sha")
        if not (is_full_sha(head) and is_full_sha(expected)):
            raise OrchestratorError("review identity is incomplete")
        if target_sha.lower() != head.lower() or target_sha.lower() != expected.lower():
            raise OrchestratorError("review verdict does not match the exact current target HEAD")

        updated = copy.deepcopy(state)
        updated["review"]["current_verdict"] = verdict
        updated["review"]["current_findings"] = copy.deepcopy(findings or [])
        updated["review"]["approval_valid"] = verdict == "APPROVED_TO_MERGE"
        save_task(project_root, updated)
        _append_jsonl(
            task_dir(project_root, updated["identity"]["id"]) / "review-history.jsonl",
            {
                "round": updated["review"]["round"],
                "target_sha": target_sha.lower(),
                "verdict": verdict,
                "findings": copy.deepcopy(findings or []),
            },
        )

        if verdict == "NEEDS_HUMAN_DECISION":
            return transition_task(project_root, "HUMAN_DECISION", "external reviewer requires human decision", task_id=updated["identity"]["id"])
        if verdict == "APPROVED_TO_MERGE":
            state = transition_task(project_root, "RELEASE_GATE", "external reviewer approved exact current HEAD", task_id=updated["identity"]["id"])
            state = copy.deepcopy(state)
            state["release"]["approved_sha"] = target_sha.lower()
            state["release"]["status"] = "READY_FOR_HUMAN_RELEASE"
            save_task(project_root, state)
            return state

        current = int(updated["review"]["round"])
        maximum = int(updated["review"]["max_rounds"])
        if current >= maximum:
            return transition_task(project_root, "REVIEW_LIMIT_REACHED", "review round limit reached with REQUEST_CHANGES", task_id=updated["identity"]["id"])
        return transition_task(project_root, "FIXING", "reviewer requested changes", task_id=updated["identity"]["id"])
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def resume(project_root: str | Path, *, task_id: str | None = None) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        # C2 invalidates stale project discovery on resume before downstream roles consume it.
        ensure_project_context(project_root, refresh_if_stale=True)
        # Recovery is intentionally observational in B6. Git/GitHub reconciliation
        # remains mandatory before re-entering REVIEWING and is performed by the
        # existing delivery helpers/B7 hardening.
        create_checkpoint(project_root, state, reason="RECOVERY", resume_hint=f"continue from {state['lifecycle']['current_state']}")
        return load_task(project_root, state["identity"]["id"])
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def _load_checks(path: str | Path) -> list[CheckSpec]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise OrchestratorError("checks file must contain a JSON array")
    return [CheckSpec.from_dict(x) for x in data]


def execute_release(project_root: str | Path, *, task_id: str | None = None, authorize: bool = False) -> dict[str, Any]:
    try:
        state = load_task(project_root, task_id)
        if state["lifecycle"]["current_state"] != "RELEASE_GATE":
            raise OrchestratorError("task is not in RELEASE_GATE")
            
        if state["release"].get("status") != "READY_FOR_HUMAN_RELEASE":
            raise OrchestratorError("task is not READY_FOR_HUMAN_RELEASE")
            
        if not authorize:
            raise OrchestratorError("explicit --authorize flag is required to release")
            
        pr_number = state["delivery"].get("pr_number")
        if not pr_number:
            raise OrchestratorError("cannot release: PR number is missing from delivery state")
            
        import subprocess
        
        # Execute squash and merge
        try:
            subprocess.run(
                ["gh", "pr", "merge", str(pr_number), "--squash", "--delete-branch"],
                cwd=str(Path(project_root).resolve()),
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as exc:
            raise OrchestratorError(f"GitHub CLI merge failed: {exc.stderr}") from exc
            
        # Transition to APPROVED
        state = transition_task(project_root, "APPROVED", "human authorized release", task_id=state["identity"]["id"])
        state = copy.deepcopy(state)
        state["release"]["status"] = "MERGED"
        save_task(project_root, state)
        
        return state
    except TaskStoreError as exc:
        raise OrchestratorError(str(exc)) from exc


def main() -> None:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    ap = argparse.ArgumentParser(description="gemini-and-chatgpt v2 MVP-1 orchestrator")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("start")
    p.add_argument("--root", default=".")
    p.add_argument("--request", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--task-id")
    p.add_argument("--max-rounds", type=int, default=5)
    p.add_argument("--files", type=int)
    p.add_argument("--components", type=int)
    p.add_argument("--kind")
    p.add_argument("--ambiguous", action="store_true")

    p = sp.add_parser("init")
    p.add_argument("--root", default=".")
    p.add_argument("--request", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--task-id")
    p.add_argument("--max-rounds", type=int, default=5)

    p = sp.add_parser("classify")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--files", type=int)
    p.add_argument("--components", type=int)
    p.add_argument("--kind")
    p.add_argument("--ambiguous", action="store_true")

    for name in ("plan-ready", "architect-ready", "implement", "resume", "review"):
        p = sp.add_parser(name)
        p.add_argument("--root", default=".")
        p.add_argument("--task-id")

    p = sp.add_parser("begin-verify")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--candidate-sha", required=True)
    p.add_argument("--branch")
    p.add_argument("--changed-file", action="append", default=[])

    p = sp.add_parser("verify")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--candidate-sha", required=False)
    p.add_argument("--checks", default="")
    p.add_argument("--branch")
    p.add_argument("--changed-file", action="append", default=[])
    p.add_argument("--timeout", type=int, default=900)

    p = sp.add_parser("delivery")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--head-sha", required=True)
    p.add_argument("--pr-number", type=int, required=True)
    p.add_argument("--pr-url", required=True)
    p.add_argument("--pr-state", required=True)
    p.add_argument("--repository")
    p.add_argument("--base-branch")
    p.add_argument("--head-branch")

    p = sp.add_parser("verdict")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--verdict", choices=sorted(VERDICTS), required=True)
    p.add_argument("--target-sha", required=True)

    p = sp.add_parser("context-refresh")
    p.add_argument("--root", default=".")

    p = sp.add_parser("context-status")
    p.add_argument("--root", default=".")

    p = sp.add_parser("context-slice")
    p.add_argument("--root", default=".")
    p.add_argument("--topic", action="append", required=True)
    p.add_argument("--work-item", default="")

    p = sp.add_parser("role-context")
    p.add_argument("--root", default=".")
    p.add_argument("--role", required=True, choices=["planner", "architect", "builder", "verifier", "reviewer"])
    p.add_argument("--work-item", default="")

    p = sp.add_parser("qa-scan")
    p.add_argument("--root", default=".")

    p = sp.add_parser("cleanup")
    p.add_argument("--root", default=".")

    p = sp.add_parser("release")
    p.add_argument("--root", default=".")
    p.add_argument("--task-id")
    p.add_argument("--authorize", action="store_true", help="Explicitly authorize the release")

    args = ap.parse_args()
    started = time.monotonic()
    log_root = Path(args.root).resolve()
    logged_argv = [sys.executable, *sys.argv]
    for i, value in enumerate(logged_argv[:-1]):
        if value == "--request":
            logged_argv[i + 1] = "<task-request-redacted>"
    command_text = format_command(logged_argv)
    append_action(log_root, stage="ORCHESTRATOR", status="START", action=f"{args.cmd}", command=command_text)
    try:
        if args.cmd == "start":
            result = start_task(args.root, args.request, args.title, task_id=args.task_id, max_rounds=args.max_rounds, estimated_files=args.files, estimated_components=args.components, explicit_kind=args.kind, ambiguity=args.ambiguous)
        elif args.cmd == "init":
            result = initialize_task(args.root, args.request, args.title, task_id=args.task_id, max_rounds=args.max_rounds)
        elif args.cmd == "classify":
            result = classify_and_route(args.root, task_id=args.task_id, estimated_files=args.files, estimated_components=args.components, explicit_kind=args.kind, ambiguity=args.ambiguous)
        elif args.cmd == "plan-ready":
            result = mark_plan_ready(args.root, task_id=args.task_id)
        elif args.cmd == "architect-ready":
            result = mark_architecture_ready(args.root, task_id=args.task_id)
        elif args.cmd == "implement":
            result = begin_implementation(args.root, task_id=args.task_id)
        elif args.cmd == "resume":
            result = resume(args.root, task_id=args.task_id)
        elif args.cmd == "review":
            result = enter_review(args.root, task_id=args.task_id)
        elif args.cmd == "begin-verify":
            result = begin_verification(args.root, args.candidate_sha, task_id=args.task_id, branch=args.branch, changed_files=args.changed_file)
        elif args.cmd == "verify":
            candidate_sha = args.candidate_sha
            if not candidate_sha:
                import subprocess
                candidate_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(log_root), text=True).strip()
            checks = _load_checks(args.checks) if args.checks else []
            result, evidence = verify_candidate(args.root, candidate_sha, checks, task_id=args.task_id, branch=args.branch, changed_files=args.changed_file, timeout_seconds=args.timeout)
            duration_ms = int((time.monotonic() - started) * 1000)
            append_action(log_root, stage="ORCHESTRATOR", status="PASS", action="verify", command=command_text, duration_ms=duration_ms, detail={"lifecycle_state": result.get("lifecycle", {}).get("current_state"), "evidence_count": len(evidence)})
            print(json.dumps({"state": result, "evidence": evidence, "action_log": str(action_log_path(log_root))}, indent=2, ensure_ascii=False))
            return
        elif args.cmd == "delivery":
            result = sync_delivery(args.root, head_sha=args.head_sha, pr_number=args.pr_number, pr_url=args.pr_url, pr_state=args.pr_state, repository=args.repository, base_branch=args.base_branch, head_branch=args.head_branch, task_id=args.task_id)
        elif args.cmd == "context-refresh":
            result = ensure_project_context(args.root, refresh_if_stale=True)
        elif args.cmd == "context-status":
            context = load_context(args.root)
            result = context_freshness(args.root, context)
        elif args.cmd == "context-slice":
            context = load_context(args.root)
            status = context_freshness(args.root, context)
            if status["status"] != "FRESH":
                raise OrchestratorError(f"project context is STALE: {status['reasons']}")
            result = slice_context(context, args.topic, work_item=args.work_item)
        elif args.cmd == "role-context":
            context = load_context(args.root)
            status = context_freshness(args.root, context)
            if status["status"] != "FRESH":
                raise OrchestratorError(f"project context is STALE: {status['reasons']}")
            topics = []
            if args.role == "planner":
                topics = ["architecture", "modules", "stack", "conventions", "known_risks"]
            elif args.role == "architect":
                topics = ["architecture", "stack", "known_risks"]
            elif args.role == "builder":
                topics = ["modules", "conventions", "environment"]
            elif args.role == "verifier":
                topics = ["commands", "conventions", "stack"]
            
            if topics:
                result = slice_context(context, topics, work_item=args.work_item)
                result["role"] = args.role
            else:
                result = {"role": args.role, "context": {}}
        elif args.cmd == "qa-scan":
            from project_health_scanner import scan_health
            result = scan_health(args.root)
        elif args.cmd == "cleanup":
            from task_store import archive_completed_tasks
            count = archive_completed_tasks(args.root)
            result = {"archived_tasks": count}
        elif args.cmd == "release":
            result = execute_release(args.root, task_id=args.task_id, authorize=args.authorize)
        else:
            result = record_review_verdict(args.root, args.verdict, args.target_sha, task_id=args.task_id)
        duration_ms = int((time.monotonic() - started) * 1000)
        detail = {}
        if isinstance(result, dict):
            lifecycle = result.get("lifecycle") if isinstance(result.get("lifecycle"), dict) else {}
            if lifecycle.get("current_state"):
                detail["lifecycle_state"] = lifecycle.get("current_state")
        append_action(log_root, stage="ORCHESTRATOR", status="PASS", action=f"{args.cmd}", command=command_text, duration_ms=duration_ms, detail=detail)
        print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    except (OrchestratorError, ContextStoreError, ProjectScanError, VerificationGateError, OSError, ValueError, json.JSONDecodeError) as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        append_action(log_root, stage="ORCHESTRATOR", status="FAIL", action=f"{args.cmd}", command=command_text, duration_ms=duration_ms, detail=str(exc))
        raise SystemExit(f"orchestrator error: {exc}; action log: {action_log_path(log_root)}") from exc


if __name__ == "__main__":
    main()
