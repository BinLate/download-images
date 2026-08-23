#!/usr/bin/env python3
"""Deterministic v2 lifecycle transitions and guards.

This module is intentionally dependency-free. It owns legal lifecycle movement,
review-round bounds, and the highest-value transition guards. Storage and
checkpoint persistence are handled by task_store.py.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import datetime, timezone
from typing import Any


STATES = (
    "RECEIVED",
    "CLASSIFIED",
    "PLANNING",
    "PLAN_READY",
    "IMPLEMENTING",
    "VERIFYING",
    "PR_PREPARING",
    "REVIEWING",
    "FIXING",
    "RELEASE_GATE",
    "APPROVED",
    "HUMAN_DECISION",
    "BLOCKED",
    "FAILED",
    "REVIEW_LIMIT_REACHED",
    "ABORTED",
)

ROLES = {
    "ORCHESTRATOR",
    "PLANNER",
    "ARCHITECT",
    "BUILDER",
    "VERIFIER",
    "CONTEXT_MANAGER",
    "DELIVERY_GATE",
    "EXTERNAL_REVIEWER",
    "HUMAN",
}

TRANSITIONS = {
    "RECEIVED": {"CLASSIFIED", "ABORTED"},
    "CLASSIFIED": {"IMPLEMENTING", "PLANNING", "HUMAN_DECISION", "BLOCKED", "ABORTED"},
    "PLANNING": {"PLAN_READY", "HUMAN_DECISION", "BLOCKED", "FAILED", "ABORTED"},
    "PLAN_READY": {"IMPLEMENTING", "HUMAN_DECISION", "BLOCKED", "ABORTED"},
    "IMPLEMENTING": {"VERIFYING", "BLOCKED", "HUMAN_DECISION", "FAILED", "ABORTED"},
    "VERIFYING": {"PR_PREPARING", "IMPLEMENTING", "FIXING", "HUMAN_DECISION", "BLOCKED", "FAILED", "ABORTED"},
    "PR_PREPARING": {"REVIEWING", "BLOCKED", "HUMAN_DECISION", "FAILED", "ABORTED"},
    "REVIEWING": {"FIXING", "RELEASE_GATE", "HUMAN_DECISION", "REVIEW_LIMIT_REACHED", "BLOCKED", "FAILED", "ABORTED"},
    "FIXING": {"VERIFYING", "HUMAN_DECISION", "BLOCKED", "FAILED", "ABORTED"},
    "RELEASE_GATE": {"APPROVED", "HUMAN_DECISION", "ABORTED"},
    "REVIEW_LIMIT_REACHED": {"HUMAN_DECISION", "ABORTED"},
    "BLOCKED": {"ABORTED"},  # resume_state is handled specially.
    "HUMAN_DECISION": {"ABORTED"},  # explicit authorization is handled specially.
    "FAILED": set(),
    "APPROVED": set(),
    "ABORTED": set(),
}

HUMAN_AUTHORIZED_TARGETS = {
    "CLASSIFIED",
    "PLANNING",
    "PLAN_READY",
    "IMPLEMENTING",
    "VERIFYING",
    "PR_PREPARING",
    "REVIEWING",
    "FIXING",
    "RELEASE_GATE",
    "BLOCKED",
}

FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class StateTransitionError(ValueError):
    """Raised when a lifecycle transition violates the v2 contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_full_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(FULL_SHA_RE.fullmatch(value))


def _review_bounds(state: dict[str, Any]) -> tuple[int, int]:
    review = state.get("review") or {}
    try:
        current = int(review.get("round", 0))
        maximum = int(review.get("max_rounds", 5))
    except (TypeError, ValueError) as exc:
        raise StateTransitionError("review round values must be integers") from exc
    if maximum < 1 or maximum > 20:
        raise StateTransitionError("max review rounds must be between 1 and 20")
    if current < 0 or current > maximum:
        raise StateTransitionError(f"review round is outside configured bounds ({current}/{maximum})")
    return current, maximum


def _base_transition_allowed(
    current: str,
    target: str,
    lifecycle: dict[str, Any],
    *,
    human_authorized: bool,
) -> bool:
    if current == "BLOCKED":
        if target == "ABORTED":
            return True
        return target == lifecycle.get("resume_state")

    if current == "HUMAN_DECISION":
        if target == "ABORTED":
            return True
        return human_authorized and target in HUMAN_AUTHORIZED_TARGETS

    return target in TRANSITIONS.get(current, set())


def _guard_classification_route(state: dict[str, Any], current: str, target: str) -> None:
    classification = state.get("classification") or {}
    tier = classification.get("complexity_tier")
    risk = classification.get("risk_level")

    if target == "CLASSIFIED":
        if tier in (None, "UNCLASSIFIED") or risk in (None, "UNKNOWN"):
            raise StateTransitionError("cannot enter CLASSIFIED before classification is resolved")

    if current != "CLASSIFIED":
        return

    if classification.get("human_precheck_required") and target not in {"HUMAN_DECISION", "BLOCKED", "ABORTED"}:
        raise StateTransitionError("human precheck is required before automated work can continue")

    if target == "IMPLEMENTING" and tier != "SIMPLE":
        raise StateTransitionError("only SIMPLE tasks may route directly from CLASSIFIED to IMPLEMENTING")
    if target == "PLANNING" and tier not in {"STANDARD", "COMPLEX"}:
        raise StateTransitionError("only STANDARD or COMPLEX tasks may route from CLASSIFIED to PLANNING")


def _guard_plan_ready(state: dict[str, Any], current: str, target: str) -> None:
    if current == "PLANNING" and target == "PLAN_READY":
        plan = state.get("plan") or {}
        if not plan.get("required"):
            raise StateTransitionError("PLAN_READY requires a task with planning enabled")
        if plan.get("status") not in {"READY", "COMPLETE"}:
            raise StateTransitionError("PLAN_READY requires plan.status READY or COMPLETE")


def _guard_verification(state: dict[str, Any], current: str, target: str) -> None:
    if current != "VERIFYING" or target != "PR_PREPARING":
        return
    verification = state.get("verification") or {}
    implementation = state.get("implementation") or {}
    if verification.get("overall_status") != "PASS":
        raise StateTransitionError("PR_PREPARING requires verification PASS")
    candidate = verification.get("candidate_sha")
    implementation_candidate = implementation.get("candidate_sha")
    if not is_full_sha(candidate):
        raise StateTransitionError("PR_PREPARING requires verification bound to a full candidate SHA")
    if implementation_candidate is not None and implementation_candidate.lower() != candidate.lower():
        raise StateTransitionError("verification candidate SHA does not match implementation candidate SHA")


def _guard_review_entry(state: dict[str, Any], current: str, target: str) -> None:
    if target != "REVIEWING":
        return
    delivery = state.get("delivery") or {}
    if not delivery.get("pr_number") or not delivery.get("pr_url"):
        raise StateTransitionError("REVIEWING requires PR number and URL")
    if delivery.get("pr_state") != "OPEN":
        raise StateTransitionError("REVIEWING requires an OPEN pull request")
    head = delivery.get("head_sha")
    if not is_full_sha(head):
        raise StateTransitionError("REVIEWING requires the exact full current PR HEAD SHA")

    if current == "PR_PREPARING":
        round_no, maximum = _review_bounds(state)
        if round_no >= maximum:
            raise StateTransitionError(f"review round limit reached ({round_no}/{maximum})")


def _guard_review_exit(state: dict[str, Any], current: str, target: str) -> None:
    if current != "REVIEWING":
        return
    review = state.get("review") or {}
    delivery = state.get("delivery") or {}
    round_no, maximum = _review_bounds(state)

    if target == "FIXING":
        if review.get("current_verdict") != "REQUEST_CHANGES":
            raise StateTransitionError("FIXING requires REQUEST_CHANGES")
        if round_no >= maximum:
            raise StateTransitionError("review round limit reached; transition to REVIEW_LIMIT_REACHED")

    if target == "RELEASE_GATE":
        head = delivery.get("head_sha")
        target_sha = review.get("current_target_sha")
        if review.get("current_verdict") != "APPROVED_TO_MERGE":
            raise StateTransitionError("RELEASE_GATE requires APPROVED_TO_MERGE")
        if not review.get("approval_valid"):
            raise StateTransitionError("RELEASE_GATE requires a valid current approval")
        if not (is_full_sha(head) and is_full_sha(target_sha)) or head.lower() != target_sha.lower():
            raise StateTransitionError("review approval is not bound to the exact current PR HEAD")

    if target == "REVIEW_LIMIT_REACHED" and round_no < maximum:
        raise StateTransitionError("review limit cannot be reached before max_rounds")


def _guard_release(state: dict[str, Any], current: str, target: str) -> None:
    if current != "RELEASE_GATE" or target != "APPROVED":
        return
    release = state.get("release") or {}
    delivery = state.get("delivery") or {}
    if release.get("human_required"):
        raise StateTransitionError("human release decision is required")
    approved_sha = release.get("approved_sha")
    head = delivery.get("head_sha")
    if not (is_full_sha(approved_sha) and is_full_sha(head)) or approved_sha.lower() != head.lower():
        raise StateTransitionError("APPROVED requires release.approved_sha to equal the exact current PR HEAD")


def validate_transition(
    state: dict[str, Any],
    target: str,
    *,
    human_authorized: bool = False,
) -> None:
    lifecycle = state.get("lifecycle") or {}
    current = lifecycle.get("current_state")
    if current not in STATES:
        raise StateTransitionError(f"unknown current state: {current!r}")
    if target not in STATES:
        raise StateTransitionError(f"unknown target state: {target!r}")
    if current == target:
        raise StateTransitionError("self-transitions are not allowed")
    _review_bounds(state)

    if not _base_transition_allowed(current, target, lifecycle, human_authorized=human_authorized):
        if current == "BLOCKED" and target != "ABORTED":
            raise StateTransitionError(
                f"BLOCKED may resume only to recorded resume_state {lifecycle.get('resume_state')!r}"
            )
        if current == "HUMAN_DECISION" and target != "ABORTED":
            raise StateTransitionError("HUMAN_DECISION requires explicit human authorization")
        raise StateTransitionError(f"illegal transition: {current} -> {target}")

    _guard_classification_route(state, current, target)
    _guard_plan_ready(state, current, target)
    _guard_verification(state, current, target)
    _guard_review_entry(state, current, target)
    _guard_review_exit(state, current, target)
    _guard_release(state, current, target)


def transition_state(
    state: dict[str, Any],
    target: str,
    reason: str,
    *,
    actor: str = "ORCHESTRATOR",
    human_authorized: bool = False,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(reason, str) or not reason.strip():
        raise StateTransitionError("transition reason must be non-empty")
    if actor not in ROLES:
        raise StateTransitionError(f"unknown transition actor: {actor}")

    validate_transition(state, target, human_authorized=human_authorized)
    result = copy.deepcopy(state)
    lifecycle = result["lifecycle"]
    current = lifecycle["current_state"]
    timestamp = now or utc_now()

    if current == "PR_PREPARING" and target == "REVIEWING":
        result["review"]["round"] = int(result["review"].get("round", 0)) + 1
        result["review"]["current_target_sha"] = result["delivery"]["head_sha"]

    if current == "REVIEWING" and target == "RELEASE_GATE":
        result["release"]["approved_sha"] = result["delivery"]["head_sha"]

    resume_state = lifecycle.get("resume_state")
    if target in {"BLOCKED", "HUMAN_DECISION"}:
        resume_state = current
    elif current in {"BLOCKED", "HUMAN_DECISION"}:
        resume_state = None

    lifecycle.update(
        {
            "previous_state": current,
            "current_state": target,
            "state_entered_at": timestamp,
            "transition_reason": reason.strip(),
            "resume_state": resume_state,
        }
    )
    result["identity"]["updated_at"] = timestamp

    history = {
        "from": current,
        "to": target,
        "timestamp": timestamp,
        "reason": reason.strip(),
        "actor": actor,
    }
    if human_authorized:
        history["human_authorized"] = True
    return result, history


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect deterministic v2 lifecycle rules")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("transitions", help="show static transition graph")
    p.add_argument("--state", choices=STATES)

    p = sp.add_parser("check", help="validate a transition against a task-state JSON file")
    p.add_argument("--file", required=True)
    p.add_argument("--to", choices=STATES, required=True)
    p.add_argument("--human-authorized", action="store_true")

    args = ap.parse_args()
    if args.cmd == "transitions":
        if args.state:
            print(json.dumps({args.state: sorted(TRANSITIONS.get(args.state, set()))}, indent=2))
        else:
            print(json.dumps({k: sorted(v) for k, v in TRANSITIONS.items()}, indent=2, sort_keys=True))
        return

    state = json.loads(open(args.file, encoding="utf-8").read())
    try:
        validate_transition(state, args.to, human_authorized=args.human_authorized)
    except StateTransitionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(2)
    print(json.dumps({"ok": True, "from": state["lifecycle"]["current_state"], "to": args.to}))


if __name__ == "__main__":
    main()
