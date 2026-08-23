#!/usr/bin/env python3
"""Durable v2 plan graph storage and deterministic Markdown projection."""
from __future__ import annotations

import argparse
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from task_store import TaskStoreError, load_task, save_task, task_dir, validate_task_state

SCHEMA_VERSION = "2.0.0"
WORK_STATUSES = {"PENDING", "READY", "IN_PROGRESS", "VERIFYING", "DONE", "BLOCKED", "SKIPPED_WITH_REASON"}
OWNER_ROLES = {"PLANNER", "ARCHITECT", "BUILDER", "VERIFIER", "DELIVERY_GATE"}

class PlanStoreError(RuntimeError):
    pass


def plan_path(project_root: str | Path, task_id: str) -> Path:
    return task_dir(project_root, task_id) / "plan.json"


def plan_md_path(project_root: str | Path, task_id: str) -> Path:
    return task_dir(project_root, task_id) / "plan.md"


def _atomic_write(path: Path, text: str) -> None:
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
        tmp.unlink(missing_ok=True)


def _items_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in plan["work_items"]}


def validate_plan(plan: dict[str, Any], *, expected_task_id: str | None = None) -> None:
    required = {
        "schema_version", "task_id", "goal", "in_scope", "out_of_scope", "constraints", "assumptions",
        "acceptance_criteria", "risk_level", "risk_notes", "work_items", "release_constraints",
    }
    allowed = required | {"allow_parallelism"}
    if not set(plan).issubset(allowed) or not required.issubset(set(plan)):
        raise PlanStoreError(f"invalid plan shape; missing={sorted(required-set(plan))} extra={sorted(set(plan)-allowed)}")
    if plan["schema_version"] != SCHEMA_VERSION:
        raise PlanStoreError("unsupported plan schema version")
    if expected_task_id and plan["task_id"] != expected_task_id:
        raise PlanStoreError("plan task_id does not match task state")
    if not isinstance(plan["goal"], str) or not plan["goal"].strip():
        raise PlanStoreError("plan goal must be non-empty")
    if "allow_parallelism" in plan and not isinstance(plan["allow_parallelism"], bool):
        raise PlanStoreError("allow_parallelism must be a boolean")
    for field in ("in_scope", "out_of_scope", "constraints", "assumptions", "acceptance_criteria", "risk_notes", "release_constraints"):
        if not isinstance(plan[field], list) or not all(isinstance(x, str) and x.strip() for x in plan[field]):
            raise PlanStoreError(f"{field} must be an array of non-empty strings")
    if plan["risk_level"] not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        raise PlanStoreError("invalid plan risk_level")
    if not isinstance(plan["work_items"], list) or not plan["work_items"]:
        raise PlanStoreError("planned task requires at least one work item")

    ids: list[str] = []
    for item in plan["work_items"]:
        required_item = {"id", "owner_role", "objective", "scope_hints", "dependencies", "verification", "status"}
        allowed = required_item | {"skip_reason"}
        if not isinstance(item, dict) or not required_item.issubset(item) or not set(item).issubset(allowed):
            raise PlanStoreError("invalid work item shape")
        if not isinstance(item["id"], str) or not item["id"].startswith("W") or not item["id"][1:].isdigit() or int(item["id"][1:]) < 1:
            raise PlanStoreError(f"invalid work item id: {item.get('id')!r}")
        if item["id"] in ids:
            raise PlanStoreError(f"duplicate work item id: {item['id']}")
        ids.append(item["id"])
        if item["owner_role"] not in OWNER_ROLES:
            raise PlanStoreError("invalid owner role")
        if item["status"] not in WORK_STATUSES:
            raise PlanStoreError("invalid work item status")
        if not isinstance(item["objective"], str) or not item["objective"].strip():
            raise PlanStoreError("work item objective must be non-empty")
        for field in ("scope_hints", "dependencies", "verification"):
            if not isinstance(item[field], list) or not all(isinstance(x, str) for x in item[field]):
                raise PlanStoreError(f"work item {field} must be a string array")
        if len(set(item["dependencies"])) != len(item["dependencies"]):
            raise PlanStoreError("work item dependencies must be unique")
        if item["status"] == "SKIPPED_WITH_REASON" and not str(item.get("skip_reason") or "").strip():
            raise PlanStoreError("SKIPPED_WITH_REASON requires skip_reason")

    known = set(ids)
    for item in plan["work_items"]:
        unknown = set(item["dependencies"]) - known
        if unknown:
            raise PlanStoreError(f"unknown dependencies for {item['id']}: {sorted(unknown)}")
        if item["id"] in item["dependencies"]:
            raise PlanStoreError(f"work item {item['id']} cannot depend on itself")

    # Kahn cycle detection.
    indegree = {wid: 0 for wid in ids}
    children = {wid: [] for wid in ids}
    for item in plan["work_items"]:
        for dep in item["dependencies"]:
            indegree[item["id"]] += 1
            children[dep].append(item["id"])
    queue = [wid for wid in ids if indegree[wid] == 0]
    visited = 0
    while queue:
        wid = queue.pop(0)
        visited += 1
        for child in children[wid]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(ids):
        raise PlanStoreError("plan dependency graph contains a cycle")


def derive_ready(plan: dict[str, Any]) -> dict[str, Any]:
    validate_plan(plan)
    result = copy.deepcopy(plan)
    by_id = _items_by_id(result)
    completed = {wid for wid, item in by_id.items() if item["status"] in {"DONE", "SKIPPED_WITH_REASON"}}
    for item in result["work_items"]:
        if item["status"] == "PENDING" and all(dep in completed for dep in item["dependencies"]):
            item["status"] = "READY"
    return result


def render_markdown(plan: dict[str, Any]) -> str:
    validate_plan(plan)
    lines = [
        f"# Plan — {plan['task_id']}", "", f"## Goal", "", plan["goal"], "",
        "## Acceptance criteria", "",
    ]
    lines += [f"- {x}" for x in plan["acceptance_criteria"]] or ["- None recorded"]
    lines += ["", "## Scope", "", "### In scope", ""]
    lines += [f"- {x}" for x in plan["in_scope"]] or ["- None recorded"]
    lines += ["", "### Out of scope", ""]
    lines += [f"- {x}" for x in plan["out_of_scope"]] or ["- None recorded"]
    lines += ["", f"## Risk", "", f"Level: **{plan['risk_level']}**", ""]
    lines += [f"- {x}" for x in plan["risk_notes"]] or ["- No additional risk notes"]
    lines += ["", "## Work items", ""]
    for item in plan["work_items"]:
        deps = ", ".join(item["dependencies"]) or "none"
        lines += [
            f"### {item['id']} — {item['objective']}", "",
            f"- Owner: `{item['owner_role']}`",
            f"- Status: `{item['status']}`",
            f"- Dependencies: {deps}",
        ]
        if item["scope_hints"]:
            lines.append(f"- Scope: {', '.join(item['scope_hints'])}")
        if item["verification"]:
            lines.append("- Verification:")
            lines += [f"  - {v}" for v in item["verification"]]
        if item.get("skip_reason"):
            lines.append(f"- Skip reason: {item['skip_reason']}")
        lines.append("")
    lines += ["## Release constraints", ""]
    lines += [f"- {x}" for x in plan["release_constraints"]] or ["- None recorded"]
    return "\n".join(lines).rstrip() + "\n"


def sync_task_state_from_plan(state: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    validate_task_state(state, expected_task_id=plan["task_id"])
    validate_plan(plan, expected_task_id=state["identity"]["id"])
    result = copy.deepcopy(state)
    completed = [i["id"] for i in plan["work_items"] if i["status"] in {"DONE", "SKIPPED_WITH_REASON"}]
    remaining = [i["id"] for i in plan["work_items"] if i["status"] not in {"DONE", "SKIPPED_WITH_REASON"}]
    active = [i["id"] for i in plan["work_items"] if i["status"] in {"IN_PROGRESS", "VERIFYING"}]
    ready = [i["id"] for i in plan["work_items"] if i["status"] == "READY"]
    
    current_items = list(active)
    
    allow_parallelism = plan.get("allow_parallelism", False)
    max_concurrency = 2 if allow_parallelism else 1
    
    by_id = _items_by_id(plan)
    
    def _scopes_overlap(item1_id: str, item2_id: str) -> bool:
        hints1 = set(by_id[item1_id].get("scope_hints", []))
        hints2 = set(by_id[item2_id].get("scope_hints", []))
        return bool(hints1 & hints2)
        
    for r in ready:
        if len(current_items) >= max_concurrency:
            break
        if not any(_scopes_overlap(r, c) for c in current_items):
            current_items.append(r)
            
    if not current_items and remaining:
        current_items.append(remaining[0])
        
    current = current_items[0] if current_items else None

    rel = f".ai/tasks/{plan['task_id']}/plan.json"
    result["plan"].update({
        "required": True,
        "status": "COMPLETE" if not remaining else "READY",
        "plan_path": rel,
        "work_item_count": len(plan["work_items"]),
        "completed_count": len(completed),
        "current_work_item": current,
        "current_work_items": current_items,
    })
    result["requirements"].update({
        "goal": plan["goal"],
        "in_scope": list(plan["in_scope"]),
        "out_of_scope": list(plan["out_of_scope"]),
        "constraints": list(plan["constraints"]),
        "acceptance_criteria": list(plan["acceptance_criteria"]),
        "release_constraints": list(plan["release_constraints"]),
        "assumptions": list(plan["assumptions"]),
    })
    result["implementation"]["work_items_completed"] = completed
    result["implementation"]["work_items_remaining"] = remaining
    validate_task_state(result, expected_task_id=plan["task_id"])
    return result


def save_plan(project_root: str | Path, plan: dict[str, Any], *, sync_state: bool = True) -> tuple[Path, Path]:
    task_id = plan.get("task_id")
    validate_plan(plan, expected_task_id=task_id)
    task = load_task(project_root, task_id)
    if task["classification"]["complexity_tier"] == "SIMPLE" or not task["classification"].get("planner_required"):
        raise PlanStoreError("full plan is reserved for tasks requiring Planner")
    if task["classification"]["risk_level"] != plan["risk_level"]:
        raise PlanStoreError("plan risk_level must match task classification")

    normalized = derive_ready(plan)
    pjson = plan_path(project_root, task_id)
    pmd = plan_md_path(project_root, task_id)
    _atomic_write(pjson, json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    _atomic_write(pmd, render_markdown(normalized))
    if sync_state:
        save_task(project_root, sync_task_state_from_plan(task, normalized))
    return pjson, pmd


def load_plan(project_root: str | Path, task_id: str) -> dict[str, Any]:
    path = plan_path(project_root, task_id)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanStoreError(f"plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanStoreError(f"corrupt plan JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PlanStoreError("plan must be a JSON object")
    validate_plan(data, expected_task_id=task_id)
    return data


def update_work_item_status(project_root: str | Path, task_id: str, work_item_id: str, status: str, *, skip_reason: str | None = None) -> dict[str, Any]:
    if status not in WORK_STATUSES:
        raise PlanStoreError(f"invalid work item status: {status}")
    plan = load_plan(project_root, task_id)
    by_id = _items_by_id(plan)
    if work_item_id not in by_id:
        raise PlanStoreError(f"unknown work item: {work_item_id}")
    item = by_id[work_item_id]
    if status in {"IN_PROGRESS", "VERIFYING", "DONE"}:
        incomplete = [dep for dep in item["dependencies"] if by_id[dep]["status"] not in {"DONE", "SKIPPED_WITH_REASON"}]
        if incomplete:
            raise PlanStoreError(f"cannot advance {work_item_id}; incomplete dependencies: {incomplete}")
    item["status"] = status
    if status == "SKIPPED_WITH_REASON":
        if not (skip_reason or "").strip():
            raise PlanStoreError("skip_reason is required")
        item["skip_reason"] = skip_reason.strip()
    else:
        item.pop("skip_reason", None)
    plan = derive_ready(plan)
    save_plan(project_root, plan, sync_state=True)
    return plan


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/render/save MVP-1 task plans")
    sub = parser.add_subparsers(dest="command", required=True)
    validate_cmd = sub.add_parser("validate")
    validate_cmd.add_argument("plan")
    render_cmd = sub.add_parser("render")
    render_cmd.add_argument("plan")
    args = parser.parse_args()
    data = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    validate_plan(data)
    if args.command == "render":
        print(render_markdown(data), end="")
    else:
        print("OK")


if __name__ == "__main__":
    main()
