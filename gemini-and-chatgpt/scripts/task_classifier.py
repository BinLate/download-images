#!/usr/bin/env python3
"""Deterministic MVP-1 task classifier and risk router."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from typing import Iterable

KINDS = {
    "BUGFIX", "FEATURE", "REFACTOR", "DOCS", "CONFIG_BUILD", "TEST",
    "DEPENDENCY", "SECURITY", "ARCHITECTURE", "MAINTENANCE", "UNKNOWN",
}
TIERS = {"SIMPLE", "STANDARD", "COMPLEX"}
RISKS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

HARD_TRIGGERS = {
    "DATA_MIGRATION",
    "BREAKING_API",
    "AUTH_SECURITY",
    "PRODUCTION_INFRA",
    "DESTRUCTIVE_OPERATION",
    "CONCURRENCY_INTEGRITY",
    "MAJOR_DEPENDENCY",
    "CROSS_SERVICE_ARCHITECTURE",
}

@dataclass(frozen=True)
class Classification:
    kind: str
    complexity_tier: str
    risk_level: str
    score: int
    signals: list[str]
    planner_required: bool
    architect_required: bool
    human_precheck_required: bool


def _contains(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _infer_kind(text: str) -> str:
    rules = [
        ("SECURITY", [r"\bauth(?:entication|orization)?\b", r"\bsecurity\b", r"permission", r"credential", r"secret"]),
        ("DEPENDENCY", [r"dependency", r"dependencies", r"upgrade .*package", r"package upgrade", r"npm", r"pip", r"composer"]),
        ("ARCHITECTURE", [r"architecture", r"cross[- ]service", r"service boundary", r"broad refactor"]),
        ("DOCS", [r"\bdocs?\b", r"readme", r"documentation", r"typo", r"chính tả"]),
        ("BUGFIX", [r"\bbug\b", r"\bfix\b", r"broken", r"error", r"crash", r"không .*được", r"lỗi"]),
        ("FEATURE", [r"\bfeature\b", r"\badd\b", r"implement", r"thêm chức năng", r"tính năng"]),
        ("REFACTOR", [r"refactor", r"restructure", r"cleanup", r"clean up"]),
        ("CONFIG_BUILD", [r"\bci\b", r"build", r"config", r"configuration", r"workflow", r"docker", r"yaml", r"yml"]),
        ("TEST", [r"\btests?\b", r"coverage", r"regression suite"]),
        ("MAINTENANCE", [r"maintenance", r"chore", r"housekeeping"]),
    ]
    for kind, patterns in rules:
        if _contains(text, patterns):
            return kind
    return "UNKNOWN"


def classify_task(
    request: str,
    *,
    estimated_files: int | None = None,
    estimated_components: int | None = None,
    explicit_kind: str | None = None,
    ambiguity: bool = False,
) -> Classification:
    if not isinstance(request, str) or not request.strip():
        raise ValueError("request must be a non-empty string")
    text = request.strip()
    normalized = text.lower()
    signals: list[str] = []
    score = 0

    kind = (explicit_kind or _infer_kind(text)).upper()
    if kind not in KINDS:
        raise ValueError(f"unsupported task kind: {kind}")

    trigger_rules = [
        ("DATA_MIGRATION", 6, [r"database migration", r"schema migration", r"migrate (?:data|database|schema)", r"backfill", r"alter table"]),
        ("BREAKING_API", 6, [r"breaking api", r"breaking change", r"public api", r"remove endpoint", r"change api contract"]),
        ("AUTH_SECURITY", 7, [r"\bauthentication\b", r"\bauthorization\b", r"\bauth\b", r"permission model", r"security model", r"oauth", r"jwt", r"rbac"]),
        ("PRODUCTION_INFRA", 6, [r"production infrastructure", r"production infra", r"terraform", r"kubernetes", r"k8s", r"load balancer", r"production deploy"]),
        ("DESTRUCTIVE_OPERATION", 8, [r"destructive", r"delete all", r"drop table", r"truncate", r"irreversible", r"purge data"]),
        ("CONCURRENCY_INTEGRITY", 6, [r"concurren", r"race condition", r"data integrity", r"transaction isolation", r"locking"]),
        ("MAJOR_DEPENDENCY", 5, [r"major dependency", r"major version", r"upgrade .*\b(?:v?[0-9]+)\b.*\b(?:v?[0-9]+)\b", r"framework migration"]),
        ("CROSS_SERVICE_ARCHITECTURE", 6, [r"cross[- ]service", r"multiple services", r"service boundary", r"distributed system", r"architecture refactor"]),
    ]
    for signal, weight, patterns in trigger_rules:
        if _contains(normalized, patterns):
            signals.append(signal)
            score += weight

    if ambiguity or _contains(normalized, [r"not sure", r"maybe", r"unclear", r"ambiguous", r"không rõ", r"tùy bạn"]):
        signals.append("AMBIGUOUS_REQUIREMENTS")
        score += 2

    if estimated_files is not None:
        if estimated_files < 0:
            raise ValueError("estimated_files cannot be negative")
        if estimated_files >= 8:
            signals.append("BROAD_FILE_SCOPE")
            score += 4
        elif estimated_files >= 3:
            signals.append("MULTI_FILE_SCOPE")
            score += 2

    if estimated_components is not None:
        if estimated_components < 0:
            raise ValueError("estimated_components cannot be negative")
        if estimated_components >= 3:
            signals.append("CROSS_COMPONENT_SCOPE")
            score += 4
        elif estimated_components >= 2:
            signals.append("MULTI_COMPONENT_SCOPE")
            score += 2

    if kind in {"SECURITY", "ARCHITECTURE"}:
        score += 2
    if kind == "DEPENDENCY":
        score += 1

    hard = any(s in HARD_TRIGGERS for s in signals)
    high_human = any(s in {"AUTH_SECURITY", "PRODUCTION_INFRA", "DESTRUCTIVE_OPERATION", "DATA_MIGRATION", "BREAKING_API"} for s in signals)

    if hard or score >= 6:
        tier = "COMPLEX"
    elif score >= 2 or kind in {"FEATURE", "REFACTOR", "DEPENDENCY", "ARCHITECTURE", "SECURITY"}:
        tier = "STANDARD"
    else:
        tier = "SIMPLE"

    if "DESTRUCTIVE_OPERATION" in signals or ("AUTH_SECURITY" in signals and "PRODUCTION_INFRA" in signals):
        risk = "CRITICAL"
    elif hard or score >= 6:
        risk = "HIGH"
    elif score >= 2:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    if tier == "COMPLEX" and risk == "MEDIUM":
        risk = "HIGH"

    # De-duplicate while keeping deterministic discovery order.
    signals = list(dict.fromkeys(signals))
    return Classification(
        kind=kind,
        complexity_tier=tier,
        risk_level=risk,
        score=score,
        signals=signals,
        planner_required=tier in {"STANDARD", "COMPLEX"},
        architect_required=tier == "COMPLEX",
        human_precheck_required=high_human,
    )


def classification_dict(*args, **kwargs) -> dict:
    return asdict(classify_task(*args, **kwargs))


def apply_classification(state: dict, classification: Classification | dict) -> dict:
    payload = asdict(classification) if isinstance(classification, Classification) else dict(classification)
    required = {
        "kind", "complexity_tier", "risk_level", "score", "signals",
        "planner_required", "architect_required", "human_precheck_required",
    }
    if set(payload) != required:
        raise ValueError(f"classification fields must be exactly {sorted(required)}")
    if payload["kind"] not in KINDS or payload["complexity_tier"] not in TIERS or payload["risk_level"] not in RISKS:
        raise ValueError("classification contains invalid enum value")
    target = json.loads(json.dumps(state))
    target["classification"] = payload
    plan = target.setdefault("plan", {})
    if payload["planner_required"]:
        plan.update({"required": True, "status": "PENDING"})
    else:
        plan.update({"required": False, "status": "NOT_REQUIRED", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None})
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify a coding task into MVP-1 risk/complexity routing")
    parser.add_argument("request")
    parser.add_argument("--files", type=int, dest="estimated_files")
    parser.add_argument("--components", type=int, dest="estimated_components")
    parser.add_argument("--kind", choices=sorted(KINDS))
    parser.add_argument("--ambiguous", action="store_true")
    args = parser.parse_args()
    print(json.dumps(classification_dict(args.request, estimated_files=args.estimated_files, estimated_components=args.estimated_components, explicit_kind=args.kind, ambiguity=args.ambiguous), indent=2))


if __name__ == "__main__":
    main()
