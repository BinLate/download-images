#!/usr/bin/env python3
"""Run one complete independent ChatGPT Web review round with one external command."""
from __future__ import annotations

import argparse
import json
import os
import time
import shutil
from datetime import datetime, timezone
import subprocess
import sys
from pathlib import Path
from typing import Any

from orchestrator import OrchestratorError, enter_review, record_review_verdict, sync_delivery
from parse_review import parse as parse_review
from review_package_guard import write_manifest
from review_prompt import ReviewPromptError, build_prompt
from state_machine import is_full_sha
from task_store import TaskStoreError, load_task, task_dir
from action_log import action_log_path, append_action, format_command


class ReviewRoundError(RuntimeError):
    pass


def _run(cmd: list[str], root: Path) -> str:
    command_text = format_command(cmd)
    started = time.monotonic()
    append_action(root, stage="REVIEW_COMMAND", status="START", action=cmd[0], command=command_text)
    proc = subprocess.run(
        cmd,
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    duration_ms = int((time.monotonic() - started) * 1000)
    if proc.returncode != 0:
        append_action(root, stage="REVIEW_COMMAND", status="FAIL", action=cmd[0], command=command_text, duration_ms=duration_ms, detail=proc.stderr.strip() or proc.stdout.strip())
        raise ReviewRoundError(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}")
    append_action(root, stage="REVIEW_COMMAND", status="PASS", action=cmd[0], command=command_text, duration_ms=duration_ms)
    return proc.stdout.strip()


def _run_json(cmd: list[str], root: Path) -> dict[str, Any]:
    text = _run(cmd, root)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReviewRoundError(f"invalid JSON from {' '.join(cmd)}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReviewRoundError(f"expected JSON object from {' '.join(cmd)}")
    return value


def _full_sha(value: Any, label: str) -> str:
    text = str(value or "").lower()
    if not is_full_sha(text):
        raise ReviewRoundError(f"{label} must be a full 40-character SHA")
    return text


def _repository_from_pr_url(url: str) -> str:
    parts = url.rstrip("/").split("/")
    try:
        pull_index = parts.index("pull")
    except ValueError as exc:
        raise ReviewRoundError(f"cannot derive repository identity from PR URL: {url!r}") from exc
    if pull_index < 2:
        raise ReviewRoundError(f"invalid GitHub PR URL: {url!r}")
    return f"{parts[pull_index - 2]}/{parts[pull_index - 1]}"


def _review_guard_path(root: Path) -> Path:
    return root / ".ai" / "review-round-guard.json"


def _write_review_guard(root: Path, *, state: dict[str, Any], head: str, error: str) -> None:
    path = _review_guard_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": state.get("identity", {}).get("id"),
        "review_round": state.get("review", {}).get("round"),
        "target_head_sha": head,
        "status": "BLOCKED",
        "error": error,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _clear_review_guard(root: Path) -> None:
    _review_guard_path(root).unlink(missing_ok=True)


def _same_blocked_attempt(root: Path, state: dict[str, Any]) -> dict[str, Any] | None:
    path = _review_guard_path(root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    target = str(state.get("review", {}).get("current_target_sha") or "").lower()
    if (
        payload.get("status") == "BLOCKED"
        and payload.get("task_id") == state.get("identity", {}).get("id")
        and int(payload.get("review_round") or -1) == int(state.get("review", {}).get("round") or -2)
        and str(payload.get("target_head_sha") or "").lower() == target
    ):
        return payload
    return None


def _already_approved(root: Path, task_id: str | None) -> dict[str, Any] | None:
    state = load_task(root, task_id)
    if state.get("lifecycle", {}).get("current_state") != "RELEASE_GATE":
        return None
    approved = _full_sha(state.get("release", {}).get("approved_sha"), "approved release SHA")
    verified = _full_sha(state.get("verification", {}).get("candidate_sha"), "verified candidate")
    delivered = _full_sha(state.get("delivery", {}).get("head_sha"), "recorded delivery HEAD")
    target = _full_sha(state.get("review", {}).get("current_target_sha"), "review target")
    if state.get("review", {}).get("current_verdict") != "APPROVED_TO_MERGE" or not state.get("review", {}).get("approval_valid"):
        raise ReviewRoundError("RELEASE_GATE is not backed by a valid APPROVED_TO_MERGE verdict")
    if not (approved == verified == delivered == target):
        raise ReviewRoundError("RELEASE_GATE exact-SHA identity is inconsistent")
    pr = _run_json(
        ["gh", "pr", "view", "--json", "number,url,headRefName,headRefOid,baseRefName,baseRefOid,state"],
        root,
    )
    pr_head = _full_sha(pr.get("headRefOid"), "PR HEAD")
    local_head = _full_sha(_run(["git", "rev-parse", "HEAD"], root), "local HEAD")
    if str(pr.get("state", "")).upper() != "OPEN" or pr_head != approved or local_head != approved:
        raise ReviewRoundError("existing approval is stale because local/PR HEAD no longer matches approved SHA")
    return {
        "ok": True,
        "status": "ALREADY_APPROVED",
        "message": "This exact PR HEAD is already APPROVED_TO_MERGE; no new ChatGPT review was started.",
        "target_head_sha": approved,
        "pr_number": int(pr["number"]),
        "pr_url": str(pr["url"]),
        "lifecycle_state": "RELEASE_GATE",
        "action_log": str(action_log_path(root).relative_to(root)),
    }


def _reconcile_delivery(root: Path, task_id: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_task(root, task_id)
    current = state["lifecycle"]["current_state"]
    if current not in {"PR_PREPARING", "REVIEWING"}:
        raise ReviewRoundError(f"review round requires PR_PREPARING or REVIEWING, current state is {current}")

    # One GitHub query is enough: PR metadata carries the exact head/base identities and PR URL.
    # Do not run a separate `gh repo view` on the happy path.
    pr = _run_json(
        ["gh", "pr", "view", "--json", "number,url,headRefName,headRefOid,baseRefName,baseRefOid,state"],
        root,
    )
    if str(pr.get("state", "")).upper() != "OPEN":
        raise ReviewRoundError(f"PR must be OPEN before review; current state is {pr.get('state')!r}")
    local_head = _full_sha(_run(["git", "rev-parse", "HEAD"], root), "local HEAD")
    pr_head = _full_sha(pr.get("headRefOid"), "PR HEAD")
    _full_sha(pr.get("baseRefOid"), "PR base SHA")
    if local_head != pr_head:
        raise ReviewRoundError(f"local HEAD {local_head} does not match PR HEAD {pr_head}")

    verified = _full_sha(state.get("verification", {}).get("candidate_sha"), "verified candidate")
    if state.get("verification", {}).get("overall_status") != "PASS":
        raise ReviewRoundError("Verification Gate must be PASS before review")
    if verified != pr_head:
        raise ReviewRoundError(f"verified candidate {verified} does not match PR HEAD {pr_head}")

    if current == "PR_PREPARING":
        sync_delivery(
            root,
            head_sha=pr_head,
            pr_number=int(pr["number"]),
            pr_url=str(pr["url"]),
            pr_state="OPEN",
            repository=_repository_from_pr_url(str(pr["url"])),
            base_branch=str(pr["baseRefName"]),
            head_branch=str(pr["headRefName"]),
            task_id=state["identity"]["id"],
        )
        enter_review(root, task_id=state["identity"]["id"])
        state = load_task(root, state["identity"]["id"])
    else:
        delivery_head = _full_sha(state.get("delivery", {}).get("head_sha"), "recorded delivery HEAD")
        target = _full_sha(state.get("review", {}).get("current_target_sha"), "review target")
        if not (delivery_head == target == pr_head == verified):
            raise ReviewRoundError("REVIEWING resume identity mismatch")
    return state, pr


def _powershell() -> str:
    for name in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        found = shutil.which(name)
        if found:
            return found
    raise ReviewRoundError("PowerShell is required for ChatGPT Web DIRECT_FILL_CDP transport")


def _artifact_paths(root: Path, state: dict[str, Any]) -> dict[str, Path]:
    round_no = int(state["review"]["round"])
    review_dir = task_dir(root, state["identity"]["id"]) / "reviews" / f"round-{round_no:02d}"
    review_dir.mkdir(parents=True, exist_ok=True)
    return {
        "dir": review_dir,
        "diff": review_dir / "pr-diff.patch",
        "prompt": review_dir / "reviewer-prompt.txt",
        "response": review_dir / "reviewer-response.txt",
        "composer": review_dir / "reviewer-composer.txt",
        "transport": review_dir / "reviewer-transport-result.json",
        "result": review_dir / "review-result.json",
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _log_state_snapshot(root: Path, state: dict[str, Any]) -> None:
    detail = {
        "task_id": state.get("identity", {}).get("id"),
        "lifecycle_state": state.get("lifecycle", {}).get("current_state"),
        "complexity": state.get("classification", {}).get("complexity_tier"),
        "planner_required": state.get("classification", {}).get("planner_required"),
        "candidate_sha": state.get("verification", {}).get("candidate_sha"),
        "verification": state.get("verification", {}).get("overall_status"),
        "pr_number": state.get("delivery", {}).get("pr_number"),
        "pr_head": state.get("delivery", {}).get("head_sha"),
        "review_round": state.get("review", {}).get("round"),
    }
    append_action(root, stage="WORKFLOW_SNAPSHOT", status="INFO", action="state before independent review", detail=detail)


def main() -> None:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    ap = argparse.ArgumentParser(description="Run one full independent ChatGPT Web review round")
    ap.add_argument("--root", default=".")
    ap.add_argument("--task-id")
    ap.add_argument("--profile-dir", help="Optional dedicated reviewer Chrome profile directory")
    ap.add_argument("--response-timeout", type=int, default=300)
    ap.add_argument("--retry-blocked", action="store_true", help="Human-authorized retry of the same previously blocked review attempt")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    review_started = time.monotonic()
    append_action(root, stage="REVIEW_ROUND", status="START", action="independent ChatGPT Web review", command=format_command([sys.executable, *sys.argv]))
    try:
        approved_summary = _already_approved(root, args.task_id)
        if approved_summary is not None:
            duration_ms = int((time.monotonic() - review_started) * 1000)
            append_action(root, stage="REVIEW_ROUND", status="PASS", action="already approved; no new review started", duration_ms=duration_ms, detail={"target_head_sha": approved_summary["target_head_sha"], "status": "ALREADY_APPROVED"})
            print(json.dumps(approved_summary, indent=2, ensure_ascii=False, sort_keys=True))
            return

        state, pr = _reconcile_delivery(root, args.task_id)
        blocked = _same_blocked_attempt(root, state)
        if blocked is not None and not args.retry_blocked:
            duration_ms = int((time.monotonic() - review_started) * 1000)
            summary = {
                "ok": False,
                "status": "BLOCKED_RETRY_SUPPRESSED",
                "message": "The same task/SHA/review round already had a transport failure. Automatic whole-round retry is suppressed. Inspect the action log; retry only after human authorization with --retry-blocked.",
                "target_head_sha": blocked.get("target_head_sha"),
                "review_round": blocked.get("review_round"),
                "previous_error": blocked.get("error"),
                "action_log": str(action_log_path(root).relative_to(root)),
            }
            append_action(root, stage="REVIEW_ROUND", status="STOP", action="duplicate blocked retry suppressed", duration_ms=duration_ms, detail={"target_head_sha": blocked.get("target_head_sha"), "review_round": blocked.get("review_round")})
            print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
            return
        _log_state_snapshot(root, state)
        head = _full_sha(state["review"]["current_target_sha"], "review target")
        base = _full_sha(pr.get("baseRefOid"), "PR base SHA")
        artifacts = _artifact_paths(root, state)

        # The PR metadata already gave us exact base/head SHAs. Build the review diff locally
        # instead of paying for a second GitHub network call (`gh pr diff`).
        diff = _run(["git", "diff", "--binary", "--find-renames", f"{base}...{head}", "--"], root)
        artifacts["diff"].write_text(diff + ("\n" if diff else ""), encoding="utf-8")

        prompt_started = time.monotonic()
        prompt = build_prompt(root, task_id=state["identity"]["id"], diff_context=diff)
        artifacts["prompt"].write_text(prompt, encoding="utf-8")
        manifest = write_manifest(artifacts["prompt"])
        append_action(root, stage="REVIEW_PACKAGE", status="PASS", action="generated immutable reviewer package", duration_ms=int((time.monotonic() - prompt_started) * 1000), detail={"prompt": str(artifacts["prompt"].relative_to(root)), "lines": manifest.get("canonical_lines"), "sha256": manifest.get("canonical_sha256")})

        script = Path(__file__).with_name("direct_fill_review_prompt.ps1")
        cmd = [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-PromptPath",
            str(artifacts["prompt"]),
            "-ReadbackPath",
            str(artifacts["composer"]),
            "-ResponsePath",
            str(artifacts["response"]),
            "-ResultPath",
            str(artifacts["transport"]),
            "-ResponseTimeoutSec",
            str(args.response_timeout),
        ]
        if args.profile_dir:
            cmd += ["-ProfileDir", str(Path(args.profile_dir).expanduser())]
        transport_command = format_command(cmd)
        transport_started = time.monotonic()
        append_action(root, stage="REVIEW_TRANSPORT", status="START", action="direct-fill and review", command=transport_command)
        transport = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        transport_duration = int((time.monotonic() - transport_started) * 1000)
        transport_result: dict[str, Any] = {}
        if artifacts["transport"].exists():
            try:
                transport_result = json.loads(artifacts["transport"].read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                transport_result = {}
        append_action(root, stage="REVIEW_TRANSPORT", status="PASS" if transport.returncode == 0 else "FAIL", action="direct-fill and review", command=transport_command, duration_ms=transport_duration, detail={"returncode": transport.returncode, "transport_path": transport_result.get("transport_path"), "browser_source": transport_result.get("browser_source"), "browser_failovers": transport_result.get("browser_failovers"), "review_target_reused": transport_result.get("review_target_reused"), "composer_resets": transport_result.get("composer_resets"), "insertion_attempts": transport_result.get("insertion_attempts"), "sent": transport_result.get("sent"), "response_received": transport_result.get("response_received"), "error": transport_result.get("error") or transport.stderr.strip()})

        if transport.returncode == 4:
            summary = {
                "ok": False,
                "status": "REVIEWER_LOGIN_REQUIRED",
                "message": "Sign in once in the reviewer Chrome window, then rerun the same review_round.py command.",
                "review_round": state["review"]["round"],
                "target_head_sha": head,
                "artifacts": {k: str(v.relative_to(root)) for k, v in artifacts.items() if k != "dir"},
                "transport": transport_result,
                "action_log": str(action_log_path(root).relative_to(root)),
            }
            print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
            raise SystemExit(4)
        if transport.returncode != 0:
            transport_error = transport_result.get("error") or transport.stderr.strip() or transport.stdout.strip()
            _write_review_guard(root, state=state, head=head, error=str(transport_error))
            raise ReviewRoundError(
                f"reviewer browser transport failed ({transport.returncode}): "
                f"{transport.stderr.strip() or transport.stdout.strip()}"
            )
        if not transport_result.get("sent") or not transport_result.get("response_received"):
            raise ReviewRoundError("reviewer transport returned success without sent=true and response_received=true")

        response_text = artifacts["response"].read_text(encoding="utf-8")
        parsed = parse_review(response_text)
        if not parsed.get("ok"):
            parsed["expected_head_sha"] = head
            _write_json(artifacts["result"], parsed)
            raise ReviewRoundError(f"reviewer response is malformed: {parsed.get('error')}")
        if parsed.get("target_head_sha") != head:
            parsed = {
                "ok": False,
                "verdict": "NEEDS_HUMAN_DECISION",
                "error": "HEAD SHA mismatch",
                "target_head_sha": parsed.get("target_head_sha"),
                "expected_head_sha": head,
            }
            _write_json(artifacts["result"], parsed)
            raise ReviewRoundError("reviewer response HEAD does not match exact current PR HEAD")

        _write_json(artifacts["result"], parsed)
        _clear_review_guard(root)
        final_state = record_review_verdict(
            root,
            str(parsed["verdict"]),
            head,
            findings=list(parsed.get("blocking_findings") or []),
            task_id=state["identity"]["id"],
        )
        duration_ms = int((time.monotonic() - review_started) * 1000)
        append_action(root, stage="REVIEW_ROUND", status="PASS", action="independent ChatGPT Web review", duration_ms=duration_ms, detail={"verdict": parsed["verdict"], "target_head_sha": head, "transport_path": transport_result.get("transport_path"), "browser_source": transport_result.get("browser_source")})
        summary = {
            "ok": True,
            "review_round": state["review"]["round"],
            "target_head_sha": head,
            "verdict": parsed["verdict"],
            "lifecycle_state": final_state["lifecycle"]["current_state"],
            "transport_path": transport_result.get("transport_path"),
            "browser_source": transport_result.get("browser_source"),
            "sent": transport_result.get("sent"),
            "response_received": transport_result.get("response_received"),
            "duration_ms": duration_ms,
            "action_log": str(action_log_path(root).relative_to(root)),
            "artifacts": {k: str(v.relative_to(root)) for k, v in artifacts.items() if k != "dir"},
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    except (ReviewRoundError, ReviewPromptError, OrchestratorError, TaskStoreError, OSError, ValueError) as exc:
        duration_ms = int((time.monotonic() - review_started) * 1000)
        append_action(root, stage="REVIEW_ROUND", status="FAIL", action="independent ChatGPT Web review", duration_ms=duration_ms, detail=str(exc))
        print(json.dumps({"ok": False, "status": "BLOCKED", "error": str(exc), "action_log": str(action_log_path(root).relative_to(root))}, indent=2, ensure_ascii=False))
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
