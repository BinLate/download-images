#!/usr/bin/env python3
"""Durable, normalized Project Context v2 store.

C2 extends the original 2.0.0 context with discovery provenance, stack/module
summaries, and freshness metadata. Secret values are never a supported field.
Legacy 2.0.0 contexts are upgraded in memory for compatibility.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2.1.0"
LEGACY_SCHEMA_VERSION = "2.0.0"
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMAND_KINDS = {"install", "lint", "typecheck", "test", "build"}
TOP_KEYS = {
    "schema_version",
    "project",
    "stack",
    "modules",
    "architecture",
    "conventions",
    "commands",
    "decisions",
    "known_risks",
    "environment",
    "provenance",
    "discovery",
    "updated_at",
}


class ContextStoreError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def context_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / ".ai" / "project-context.json"


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _empty_discovery() -> dict[str, Any]:
    return {
        "generated_at": None,
        "fingerprint": "0" * 64,
        "inventory_fingerprint": "0" * 64,
        "source_file_count": 0,
        "sources": [],
        "scan_limit": 0,
        "files_observed": 0,
    }


def _empty_provenance() -> dict[str, Any]:
    return {
        "commands": {kind: [] for kind in sorted(COMMAND_KINDS)},
        "stack": [],
        "modules": [],
        "conventions": [],
        "environment": [],
        "redactions": [],
    }


def upgrade_context(data: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a legacy 2.0.0 context in memory without losing normalized facts."""
    if not isinstance(data, dict):
        raise ContextStoreError("project context must be an object")
    if data.get("schema_version") == SCHEMA_VERSION:
        return copy.deepcopy(data)
    if data.get("schema_version") != LEGACY_SCHEMA_VERSION:
        raise ContextStoreError("unsupported project-context schema version")
    result = copy.deepcopy(data)
    result["schema_version"] = SCHEMA_VERSION
    result.setdefault("stack", {"languages": [], "package_managers": [], "frameworks": []})
    result.setdefault("modules", [])
    result.setdefault("provenance", _empty_provenance())
    result.setdefault("discovery", _empty_discovery())
    return result


def validate_context(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ContextStoreError("project context must be an object")
    if data.get("schema_version") == LEGACY_SCHEMA_VERSION:
        data = upgrade_context(data)
    if set(data) != TOP_KEYS:
        raise ContextStoreError(
            f"invalid project-context shape; missing={sorted(TOP_KEYS-set(data))} extra={sorted(set(data)-TOP_KEYS)}"
        )
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ContextStoreError("unsupported project-context schema version")

    project = data.get("project")
    if not isinstance(project, dict) or set(project) - {"name", "root", "repository"}:
        raise ContextStoreError("invalid project object")
    if not isinstance(project.get("name"), str) or not project["name"]:
        raise ContextStoreError("project.name is required")
    if not isinstance(project.get("root"), str) or not project["root"]:
        raise ContextStoreError("project.root is required")
    repository = project.get("repository")
    if repository is not None and (not isinstance(repository, str) or repository.count("/") != 1):
        raise ContextStoreError("project.repository must be owner/repo or null")

    stack = data.get("stack")
    if not isinstance(stack, dict) or set(stack) != {"languages", "package_managers", "frameworks"}:
        raise ContextStoreError("invalid stack shape")
    languages = stack["languages"]
    if not isinstance(languages, list):
        raise ContextStoreError("stack.languages must be an array")
    for item in languages:
        if not isinstance(item, dict) or set(item) != {"name", "file_count"}:
            raise ContextStoreError("invalid language item")
        if not isinstance(item["name"], str) or not item["name"] or not isinstance(item["file_count"], int) or item["file_count"] < 1:
            raise ContextStoreError("invalid language item values")
    for key in ("package_managers", "frameworks"):
        values = stack[key]
        if not isinstance(values, list) or any(not isinstance(v, str) or not v for v in values):
            raise ContextStoreError(f"stack.{key} must be a list of non-empty strings")
        if len(values) != len(set(values)):
            raise ContextStoreError(f"stack.{key} must be unique")

    modules = data.get("modules")
    if not isinstance(modules, list):
        raise ContextStoreError("modules must be an array")
    for module in modules:
        if not isinstance(module, dict) or set(module) != {"path", "source_file_count", "language_hints"}:
            raise ContextStoreError("invalid module item")
        if not isinstance(module["path"], str) or not module["path"]:
            raise ContextStoreError("module.path is required")
        if not isinstance(module["source_file_count"], int) or module["source_file_count"] < 1:
            raise ContextStoreError("module.source_file_count must be positive")
        if not isinstance(module["language_hints"], list) or any(not isinstance(v, str) or not v for v in module["language_hints"]):
            raise ContextStoreError("module.language_hints must be strings")

    for key in ("architecture", "conventions", "commands", "environment", "provenance", "discovery"):
        if not isinstance(data.get(key), dict):
            raise ContextStoreError(f"{key} must be an object")
    if set(data["architecture"]) != {"summary", "components", "boundaries", "constraints"}:
        raise ContextStoreError("invalid architecture context shape")
    for key in ("components", "boundaries", "constraints"):
        values = data["architecture"][key]
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ContextStoreError(f"architecture.{key} must be strings")
    if not isinstance(data["architecture"]["summary"], str):
        raise ContextStoreError("architecture.summary must be a string")

    if set(data["conventions"]) != {"coding", "testing", "git"}:
        raise ContextStoreError("invalid conventions shape")
    for key in ("coding", "testing", "git"):
        values = data["conventions"][key]
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ContextStoreError(f"conventions.{key} must be strings")

    if set(data["commands"]) != COMMAND_KINDS:
        raise ContextStoreError("invalid commands shape")
    for kind in COMMAND_KINDS:
        values = data["commands"].get(kind)
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ContextStoreError(f"commands.{kind} must be a list of non-empty strings")

    if set(data["environment"]) != {"required_variable_names"}:
        raise ContextStoreError("environment may store required_variable_names only; secret values are forbidden")
    names = data["environment"]["required_variable_names"]
    if not isinstance(names, list) or any(not isinstance(n, str) or not ENV_NAME_RE.fullmatch(n) for n in names):
        raise ContextStoreError("invalid environment variable name list")
    if len(names) != len(set(names)):
        raise ContextStoreError("environment variable names must be unique")

    if not isinstance(data.get("decisions"), list) or not isinstance(data.get("known_risks"), list):
        raise ContextStoreError("decisions and known_risks must be arrays")

    provenance = data["provenance"]
    if set(provenance) != {"commands", "stack", "modules", "conventions", "environment", "redactions"}:
        raise ContextStoreError("invalid provenance shape")
    if not isinstance(provenance["commands"], dict) or set(provenance["commands"]) != COMMAND_KINDS:
        raise ContextStoreError("invalid provenance.commands shape")
    for values in list(provenance["commands"].values()) + [
        provenance["stack"], provenance["modules"], provenance["conventions"], provenance["environment"], provenance["redactions"]
    ]:
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ContextStoreError("provenance entries must be string arrays")

    discovery = data["discovery"]
    if set(discovery) != {"generated_at", "fingerprint", "inventory_fingerprint", "source_file_count", "sources", "scan_limit", "files_observed"}:
        raise ContextStoreError("invalid discovery shape")
    if discovery["generated_at"] is not None and not isinstance(discovery["generated_at"], str):
        raise ContextStoreError("discovery.generated_at must be string or null")
    if not isinstance(discovery["fingerprint"], str) or not SHA256_RE.fullmatch(discovery["fingerprint"]):
        raise ContextStoreError("discovery.fingerprint must be sha256")
    if not isinstance(discovery["inventory_fingerprint"], str) or not SHA256_RE.fullmatch(discovery["inventory_fingerprint"]):
        raise ContextStoreError("discovery.inventory_fingerprint must be sha256")
    if not isinstance(discovery["source_file_count"], int) or discovery["source_file_count"] < 0:
        raise ContextStoreError("discovery.source_file_count must be non-negative")
    if not isinstance(discovery["scan_limit"], int) or discovery["scan_limit"] < 0:
        raise ContextStoreError("discovery.scan_limit must be non-negative")
    if not isinstance(discovery["files_observed"], int) or discovery["files_observed"] < 0:
        raise ContextStoreError("discovery.files_observed must be non-negative")
    if not isinstance(discovery["sources"], list):
        raise ContextStoreError("discovery.sources must be an array")
    for source in discovery["sources"]:
        if not isinstance(source, dict) or set(source) != {"path", "size", "mtime_ns", "sha256"}:
            raise ContextStoreError("invalid discovery source")
        if not isinstance(source["path"], str) or not source["path"] or source["path"].startswith("/") or ".." in Path(source["path"]).parts:
            raise ContextStoreError("discovery source path must be safe relative path")
        if not isinstance(source["size"], int) or source["size"] < 0 or not isinstance(source["mtime_ns"], int) or source["mtime_ns"] < 0:
            raise ContextStoreError("invalid discovery source metadata")
        if not isinstance(source["sha256"], str) or not SHA256_RE.fullmatch(source["sha256"]):
            raise ContextStoreError("invalid discovery source sha256")


def new_context(project_root: str | Path, name: str, repository: str | None = None, *, timestamp: str | None = None) -> dict[str, Any]:
    if not name.strip():
        raise ContextStoreError("project name must be non-empty")
    now = timestamp or utc_now()
    data = {
        "schema_version": SCHEMA_VERSION,
        "project": {"name": name.strip(), "root": str(Path(project_root).resolve()), "repository": repository},
        "stack": {"languages": [], "package_managers": [], "frameworks": []},
        "modules": [],
        "architecture": {"summary": "", "components": [], "boundaries": [], "constraints": []},
        "conventions": {"coding": [], "testing": [], "git": []},
        "commands": {"install": [], "lint": [], "typecheck": [], "test": [], "build": []},
        "decisions": [],
        "known_risks": [],
        "environment": {"required_variable_names": []},
        "provenance": _empty_provenance(),
        "discovery": _empty_discovery(),
        "updated_at": now,
    }
    validate_context(data)
    return data


def save_context(project_root: str | Path, data: dict[str, Any], *, timestamp: str | None = None) -> Path:
    result = upgrade_context(data)
    result["updated_at"] = timestamp or utc_now()
    validate_context(result)
    path = context_path(project_root)
    _atomic_write(path, result)
    return path


def load_context(project_root: str | Path) -> dict[str, Any]:
    path = context_path(project_root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContextStoreError(f"project context not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContextStoreError(f"corrupt project context; refusing unsafe reset: {path}: {exc}") from exc
    result = upgrade_context(data)
    validate_context(result)
    return result


def init_context(project_root: str | Path, name: str, repository: str | None = None, *, overwrite: bool = False) -> dict[str, Any]:
    path = context_path(project_root)
    if path.exists() and not overwrite:
        return load_context(project_root)
    data = new_context(project_root, name, repository)
    save_context(project_root, data, timestamp=data["updated_at"])
    return data


def set_repository(data: dict[str, Any], repository: str | None) -> dict[str, Any]:
    result = upgrade_context(data)
    result["project"]["repository"] = repository
    validate_context(result)
    return result


def add_command(data: dict[str, Any], kind: str, command: str) -> dict[str, Any]:
    if kind not in COMMAND_KINDS:
        raise ContextStoreError(f"unknown command kind: {kind}")
    if not command.strip():
        raise ContextStoreError("command must be non-empty")
    result = upgrade_context(data)
    if command.strip() not in result["commands"][kind]:
        result["commands"][kind].append(command.strip())
    validate_context(result)
    return result


def require_env_name(data: dict[str, Any], name: str) -> dict[str, Any]:
    if not ENV_NAME_RE.fullmatch(name):
        raise ContextStoreError(f"invalid environment variable name: {name}")
    result = upgrade_context(data)
    names = result["environment"]["required_variable_names"]
    if name not in names:
        names.append(name)
        names.sort()
    validate_context(result)
    return result


def add_decision(data: dict[str, Any], decision: str, reason: str = "", *, timestamp: str | None = None) -> dict[str, Any]:
    if not decision.strip():
        raise ContextStoreError("decision must be non-empty")
    result = upgrade_context(data)
    result["decisions"].append({"decision": decision.strip(), "reason": reason.strip(), "recorded_at": timestamp or utc_now()})
    validate_context(result)
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Manage normalized Project Context v2")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("init")
    p.add_argument("--root", default=".")
    p.add_argument("--name", required=True)
    p.add_argument("--repository")
    p.add_argument("--overwrite", action="store_true")

    p = sp.add_parser("show")
    p.add_argument("--root", default=".")

    p = sp.add_parser("set-repository")
    p.add_argument("--root", default=".")
    p.add_argument("--repository")

    p = sp.add_parser("add-command")
    p.add_argument("--root", default=".")
    p.add_argument("--kind", choices=sorted(COMMAND_KINDS), required=True)
    p.add_argument("--command", required=True)

    p = sp.add_parser("require-env")
    p.add_argument("--root", default=".")
    p.add_argument("--name", required=True)

    p = sp.add_parser("add-decision")
    p.add_argument("--root", default=".")
    p.add_argument("--decision", required=True)
    p.add_argument("--reason", default="")

    args = ap.parse_args()
    try:
        if args.cmd == "init":
            data = init_context(args.root, args.name, args.repository, overwrite=args.overwrite)
        elif args.cmd == "show":
            data = load_context(args.root)
        elif args.cmd == "set-repository":
            data = set_repository(load_context(args.root), args.repository)
            save_context(args.root, data)
        elif args.cmd == "add-command":
            data = add_command(load_context(args.root), args.kind, args.command)
            save_context(args.root, data)
        elif args.cmd == "require-env":
            data = require_env_name(load_context(args.root), args.name)
            save_context(args.root, data)
        else:
            data = add_decision(load_context(args.root), args.decision, args.reason)
            save_context(args.root, data)
        print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
    except ContextStoreError as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
