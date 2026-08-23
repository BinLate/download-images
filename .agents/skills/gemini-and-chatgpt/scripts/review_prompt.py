#!/usr/bin/env python3
"""Build the minimal independent-review prompt for the exact current PR HEAD."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from state_machine import is_full_sha
from task_store import TaskStoreError, load_task, task_dir
from review_package_guard import write_manifest


class ReviewPromptError(RuntimeError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ReviewPromptError(f"corrupt JSONL at {path}:{lineno}: {exc}") from exc
        if not isinstance(row, dict):
            raise ReviewPromptError(f"invalid JSONL record at {path}:{lineno}")
        rows.append(row)
    return rows


def _bullets(values: list[Any], empty: str = "None recorded") -> str:
    clean = [str(v).strip() for v in values if str(v).strip()]
    return "\n".join(f"- {v}" for v in clean) if clean else f"- {empty}"


def _verification_rows(root: Path, state: dict[str, Any], head: str) -> list[dict[str, Any]]:
    path = task_dir(root, state["identity"]["id"]) / "verification.jsonl"
    rows = _read_jsonl(path)
    return [r for r in rows if str(r.get("candidate_sha", "")).lower() == head]


def _prior_review_summary(root: Path, state: dict[str, Any]) -> str:
    path = task_dir(root, state["identity"]["id"]) / "review-history.jsonl"
    rows = _read_jsonl(path)
    current_round = int(state["review"].get("round", 0))
    prior = [r for r in rows if int(r.get("round", 0)) < current_round]
    if not prior:
        return "- None; this is the first review round."
    lines: list[str] = []
    for row in prior[-4:]:
        lines.append(f"- Round {row.get('round')}: {row.get('verdict', 'UNKNOWN')} @ {row.get('target_sha', 'UNKNOWN')}")
        findings = row.get("findings") or []
        if not findings:
            lines.append("  - Findings: none recorded")
            continue
        for finding in findings[:12]:
            if not isinstance(finding, dict):
                continue
            fid = finding.get("id", "finding")
            text = finding.get("text") or finding.get("summary") or "finding text not recorded"
            disposition = finding.get("disposition") or finding.get("resolution") or "UNRESOLVED/NOT_RECORDED"
            rationale = finding.get("rationale")
            item = f"  - {fid}: {text} | disposition={disposition}"
            if rationale:
                item += f" | rationale={rationale}"
            lines.append(item)
    return "\n".join(lines)


def _plan_summary(root: Path, state: dict[str, Any]) -> str:
    plan_path = state.get("plan", {}).get("plan_path")
    if not plan_path:
        return "- Full planner graph not required for this task."
    path = root / plan_path
    if not path.exists():
        return "- Plan path is recorded but unavailable; reviewer should treat missing plan context as evidence gap."
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewPromptError(f"corrupt plan JSON: {exc}") from exc
    lines = []
    for item in plan.get("work_items", [])[:30]:
        lines.append(f"- {item.get('id')}: {item.get('objective')} [{item.get('status')}] owner={item.get('owner_role')}")
    return "\n".join(lines) if lines else "- No work items recorded."


def build_prompt(project_root: str | Path, *, task_id: str | None = None, contract_path: str | Path | None = None, diff_context: str | None = None) -> str:
    root = Path(project_root).resolve()
    try:
        state = load_task(root, task_id)
    except TaskStoreError as exc:
        raise ReviewPromptError(str(exc)) from exc
    if state["lifecycle"]["current_state"] != "REVIEWING":
        raise ReviewPromptError("review prompt may be built only while task is REVIEWING")
    delivery = state["delivery"]
    review = state["review"]
    head = str(delivery.get("head_sha") or "").lower()
    target = str(review.get("current_target_sha") or "").lower()
    verified = str(state["verification"].get("candidate_sha") or "").lower()
    if not (is_full_sha(head) and is_full_sha(target) and is_full_sha(verified)):
        raise ReviewPromptError("review identity requires full delivery/review/verification SHA values")
    if not (head == target == verified):
        raise ReviewPromptError("review prompt identity mismatch: PR HEAD, review target, and verified candidate must be identical")
    if str(delivery.get("pr_state") or "").upper() != "OPEN":
        raise ReviewPromptError("review prompt requires an OPEN pull request")
    if state["verification"].get("overall_status") != "PASS":
        raise ReviewPromptError("review prompt requires Verification Gate PASS for the current HEAD")

    contract = Path(contract_path) if contract_path else Path(__file__).resolve().parents[1] / "references" / "review-contract.md"
    if not contract.exists():
        raise ReviewPromptError(f"review contract not found: {contract}")
    contract_text = contract.read_text(encoding="utf-8").strip()

    req = state["requirements"]
    impl = state["implementation"]
    evidence = _verification_rows(root, state, head)
    if not evidence:
        raise ReviewPromptError("no verification evidence is bound to the current review HEAD")
    evidence_lines = []
    for r in evidence[-30:]:
        evidence_lines.append(
            f"- {r.get('check_id')} | {r.get('category')} | required={str(bool(r.get('required'))).lower()} | "
            f"status={r.get('status')} | exit_code={r.get('exit_code')} | summary={r.get('summary')}"
        )

    diff = (diff_context or "").strip()
    pr_url = str(delivery.get("pr_url") or "").strip()
    repo = str(delivery.get("repository") or "").strip()
    files_url = f"{pr_url}/files" if pr_url else f"https://github.com/{repo}/commit/{head}" if repo else ""

    if len(diff) > 4000:
        # Keep prompt lightweight: truncate huge inlined diff and direct reviewer to GitHub PR link
        diff_summary = f"Full diff contains {len(diff.splitlines())} lines. Inspect full diff and changed files on GitHub: {files_url or pr_url or 'See PR URL above'}\n\nChanged files preview:\n" + "\n".join(f"- {f}" for f in (impl.get("changed_files") or []))
        if not (impl.get("changed_files")):
            # If changed_files list is empty, include the first few diff headers
            headers = [line for line in diff.splitlines() if line.startswith("diff --git") or line.startswith("--- ") or line.startswith("+++ ")][:20]
            diff_summary += "\n" + "\n".join(headers)
        diff = diff_summary
    if not diff:
        diff = f"No inline diff supplied. Review the PR URL / current GitHub diff at: {files_url or pr_url or 'See PR URL above'}"

    prompt_id = hashlib.sha256(
        f"{state['identity']['id']}|{review.get('round')}|{head}".encode("utf-8")
    ).hexdigest()[:24]

    goal_text = req.get("goal") or state["identity"]["original_request"]

    sections = [
        "=== GEMINI_CHATGPT_REVIEW_BEGIN ===",
        f"PROMPT_ID: {prompt_id}",
        f"TARGET_HEAD_SHA: {head}",
        "",
        "# Independent Review Package",
        "",
        "## Language policy",
        "- Reviewer-facing communication is English-only.",
        "- Perform the code review, findings, rationale, test-gap analysis, and final verdict in English.",
        "- Preserve source-code identifiers, file paths, literals, and quoted task text exactly when needed; translate/explain their meaning in English rather than switching the review response language.",
        "",
        "## Task identity",
        f"- Task ID: {state['identity']['id']}",
        f"- Title: {state['identity']['normalized_title']}",
        f"- Review round: {review.get('round')}/{review.get('max_rounds')}",
        "",
        "## Goal",
        goal_text,
        "",
        "## In scope",
        _bullets(req.get("in_scope") or []),
        "",
        "## Out of scope",
        _bullets(req.get("out_of_scope") or []),
        "",
        "## Acceptance criteria",
        _bullets(req.get("acceptance_criteria") or [], "No explicit acceptance criteria recorded"),
        "",
        "## Material constraints and assumptions",
        _bullets((req.get("constraints") or []) + (req.get("assumptions") or [])),
        "",
        "## Implementation summary",
        f"- Branch: {impl.get('branch') or delivery.get('head_branch') or 'not recorded'}",
        f"- Candidate SHA: {impl.get('candidate_sha')}",
        f"- Changed files: {', '.join(impl.get('changed_files') or []) or 'not recorded'}",
        f"- Completed work items: {', '.join(impl.get('work_items_completed') or []) or 'none recorded'}",
        "",
        "## Planner work-item summary",
        _plan_summary(root, state),
        "",
        "## Pull request identity",
        f"- Repository: {delivery.get('repository')}",
        f"- PR: {delivery.get('pr_url') or delivery.get('pr_number')}",
        f"- PR Files Changed: {files_url}",
        f"- PR state: {delivery.get('pr_state')}",
        f"- Base branch: {delivery.get('base_branch')}",
        f"- Head branch: {delivery.get('head_branch')}",
        f"- TARGET_HEAD_SHA: {head}",
        f"- Review Instructions: Inspect code at {files_url or pr_url} for (1) Requirements alignment, (2) Feature correctness, (3) Security audit, (4) Feature recommendations.",
        "",
        "## Verification evidence bound to TARGET_HEAD_SHA",
        *evidence_lines,
        "",
        "## Prior blocking findings / dispositions",
        _prior_review_summary(root, state),
        "",
        "## Changed-file / diff context",
        diff,
        "",
        "## Reviewer contract",
        contract_text,
        "",
        "## Binding instruction",
        f"Review only TARGET_HEAD_SHA {head}. Return that exact 40-character SHA in the final response. If reliable supplied/live evidence shows a different HEAD, return NEEDS_HUMAN_DECISION.",
        "The delivery gate already reconciled the OPEN PR and exact HEAD before this package was generated. Direct access to a private GitHub PR is optional corroboration, not a prerequisite for approval. Do not return NEEDS_HUMAN_DECISION merely because the PR URL is private, inaccessible, or returns 404 in the reviewer browser.",
        "Base the review on the supplied exact-SHA package, diff/context, and SHA-bound verification evidence. Escalate only for an actual identity inconsistency, materially insufficient review evidence, or another substantive blocker.",
        "Respond entirely in English using the exact machine-parseable response format in the reviewer contract.",
        "Use a fresh ChatGPT Web conversation for this round; do not rely on prior reviewer chat state.",
        "",
        "=== GEMINI_CHATGPT_REVIEW_END ===",
        f"PROMPT_ID: {prompt_id}",
        f"TARGET_HEAD_SHA: {head}",
    ]
    return "\n".join(str(x) for x in sections).rstrip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Build exact-SHA independent-review prompt")
    ap.add_argument("--root", default=".")
    ap.add_argument("--task-id")
    ap.add_argument("--contract")
    ap.add_argument("--diff-file")
    ap.add_argument("--output")
    ap.add_argument("--manifest", help="Optional immutable package manifest path; defaults beside --output")
    args = ap.parse_args()
    try:
        diff = Path(args.diff_file).read_text(encoding="utf-8") if args.diff_file else None
        prompt = build_prompt(args.root, task_id=args.task_id, contract_path=args.contract, diff_context=diff)
    except ReviewPromptError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(2)
    if args.output:
        Path(args.output).write_text(prompt, encoding="utf-8")
        write_manifest(args.output, args.manifest)
    print(prompt, end="")


if __name__ == "__main__":
    main()
