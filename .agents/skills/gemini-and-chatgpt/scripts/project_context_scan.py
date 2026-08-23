#!/usr/bin/env python3
"""Deterministic, secret-safe repository discovery for Project Context v2 (C2)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from context_store import ContextStoreError, load_context, save_context, upgrade_context, validate_context

IGNORED_DIRS = {
    ".git", ".ai", ".agents", ".idea", ".vscode", "node_modules", "vendor",
    ".venv", "venv", "env", "dist", "build", "coverage", "htmlcov", "__pycache__",
    "gemini-and-chatgpt",
}
SOURCE_EXTENSIONS = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin",
    ".go": "Go", ".rs": "Rust", ".cs": "C#", ".php": "PHP", ".rb": "Ruby",
    ".swift": "Swift", ".c": "C", ".cc": "C++", ".cpp": "C++", ".h": "C/C++",
    ".vue": "Vue", ".svelte": "Svelte", ".sh": "Shell", ".ps1": "PowerShell",
}
MANIFESTS = {
    "package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.cfg",
    "tox.ini", "pytest.ini", "Makefile", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "build.gradle.kts", "composer.json", "Gemfile", "AGENTS.md", "CONTRIBUTING.md",
}
LOCKFILES = {
    "package-lock.json": "npm", "npm-shrinkwrap.json": "npm", "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn", "uv.lock": "uv", "poetry.lock": "poetry", "Pipfile.lock": "pipenv",
    "Cargo.lock": "cargo", "go.sum": "go", "composer.lock": "composer", "Gemfile.lock": "bundler",
}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret|private[_-]?key)\b\s*[=:]\s*([^\s;&|]+)"
)
ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class ProjectScanError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_ignored(root: Path, path: Path) -> bool:
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return True
    return any(part in IGNORED_DIRS for part in parts)


def iter_files(root: Path, *, max_files: int = 10000) -> Iterable[Path]:
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        dirnames[:] = sorted(x for x in dirnames if x not in IGNORED_DIRS)
        for name in sorted(filenames):
            p = d / name
            if _is_ignored(root, p):
                continue
            yield p
            count += 1
            if count >= max_files:
                return


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _source_record(root: Path, path: Path) -> dict[str, Any]:
    st = path.stat()
    return {
        "path": _rel(root, path),
        "size": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "sha256": _hash_file(path),
    }


def _fingerprint(records: list[dict[str, Any]]) -> str:
    normalized = json.dumps(records, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _source_inventory(root: Path, files: list[Path]) -> tuple[str, int]:
    items = []
    for path in files:
        if not SOURCE_EXTENSIONS.get(path.suffix.lower()):
            continue
        st = path.stat()
        items.append((_rel(root, path), st.st_size, st.st_mtime_ns))
    items.sort()
    encoded = json.dumps(items, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), len(items)


def _sanitize_command(command: str) -> tuple[str, bool]:
    redacted = False
    def repl(match: re.Match[str]) -> str:
        nonlocal redacted
        redacted = True
        full = match.group(0)
        value = match.group(1)
        return full[: full.rfind(value)] + "<redacted>"
    return SECRET_ASSIGNMENT_RE.sub(repl, command.strip()), redacted


def _git_repository(root: Path) -> str | None:
    try:
        cp = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if cp.returncode != 0:
        return None
    url = cp.stdout.strip()
    # Never persist embedded credentials.
    url = re.sub(r"https://[^/@]+@", "https://", url)
    patterns = [
        r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?$",
        r"^[^/\s]+/[^/\s]+$",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            if len(m.groups()) == 2:
                return f"{m.group(1)}/{m.group(2)}"
            return m.group(0)
    return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_pyproject(path: Path) -> dict[str, Any]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _dependency_names(package: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        obj = package.get(key)
        if isinstance(obj, dict):
            names.update(str(x).lower() for x in obj)
    return names


def _frameworks(root: Path, package: dict[str, Any], pyproject: dict[str, Any], files: set[str]) -> list[str]:
    result: set[str] = set()
    deps = _dependency_names(package)
    npm_map = {
        "react": "React", "next": "Next.js", "vue": "Vue", "nuxt": "Nuxt",
        "@angular/core": "Angular", "svelte": "Svelte", "express": "Express",
        "nestjs": "NestJS", "@nestjs/core": "NestJS", "vitest": "Vitest", "jest": "Jest",
    }
    for dep, label in npm_map.items():
        if dep in deps:
            result.add(label)
    blob = json.dumps(pyproject, ensure_ascii=False).lower()
    py_map = {
        "django": "Django", "fastapi": "FastAPI", "flask": "Flask", "pytest": "pytest",
        "pydantic": "Pydantic", "sqlalchemy": "SQLAlchemy", "ruff": "Ruff", "mypy": "mypy",
    }
    for dep, label in py_map.items():
        if dep in blob:
            result.add(label)
    if "pytest.ini" in files or "tox.ini" in files:
        result.add("pytest")
    return sorted(result)


def _commands(root: Path, package: dict[str, Any], pyproject: dict[str, Any], files: set[str]) -> tuple[dict[str, list[str]], dict[str, list[str]], list[str]]:
    commands = {k: [] for k in ("install", "lint", "typecheck", "test", "build")}
    provenance = {k: [] for k in commands}
    redactions: list[str] = []

    manager = None
    if "pnpm-lock.yaml" in files:
        manager = "pnpm"
    elif "yarn.lock" in files:
        manager = "yarn"
    elif "package-lock.json" in files or "npm-shrinkwrap.json" in files or "package.json" in files:
        manager = "npm"
    if manager:
        install_cmd = {"pnpm": "pnpm install", "yarn": "yarn install", "npm": "npm install"}[manager]
        commands["install"].append(install_cmd)
        provenance["install"].append("package.json" if (root / "package.json").exists() else next((x for x in files if x.endswith("lock.yaml") or x.endswith("lock.json")), ""))

    scripts = package.get("scripts") if isinstance(package.get("scripts"), dict) else {}
    aliases = {
        "lint": ("lint",), "typecheck": ("typecheck", "type-check", "check-types"),
        "test": ("test", "test:unit"), "build": ("build",),
    }
    prefix = {"pnpm": "pnpm", "yarn": "yarn", "npm": "npm run"}.get(manager or "npm", "npm run")
    for kind, names in aliases.items():
        for name in names:
            if name in scripts:
                cmd = f"{prefix} {name}"
                cmd, was_redacted = _sanitize_command(cmd)
                commands[kind].append(cmd)
                provenance[kind].append("package.json")
                if was_redacted:
                    redactions.append(f"commands.{kind}")
                break

    pyblob = json.dumps(pyproject, ensure_ascii=False).lower()
    if pyproject:
        if "pytest" in pyblob:
            commands["test"].append("python -m pytest")
            provenance["test"].append("pyproject.toml")
        if "ruff" in pyblob:
            commands["lint"].append("python -m ruff check .")
            provenance["lint"].append("pyproject.toml")
        if "mypy" in pyblob:
            commands["typecheck"].append("python -m mypy .")
            provenance["typecheck"].append("pyproject.toml")

    if "pytest.ini" in files and "python -m pytest" not in commands["test"]:
        commands["test"].append("python -m pytest")
        provenance["test"].append("pytest.ini")
    for kind in commands:
        commands[kind] = list(dict.fromkeys(commands[kind]))
        provenance[kind] = [p for p in dict.fromkeys(provenance[kind]) if p]
    return commands, provenance, redactions


def _env_names(root: Path) -> tuple[list[str], list[str]]:
    names: set[str] = set()
    sources: list[str] = []
    for candidate in (".env.example", ".env.sample", ".env.template"):
        path = root / candidate
        if not path.is_file():
            continue
        sources.append(candidate)
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = ENV_LINE_RE.match(line)
                if m:
                    names.add(m.group(1))
        except OSError:
            pass
    return sorted(names), sources


def scan_project(project_root: str | Path, *, max_files: int = 10000) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if not root.is_dir():
        raise ProjectScanError(f"project root not found: {root}")
    files = list(iter_files(root, max_files=max_files))
    rels = {_rel(root, p) for p in files}
    root_names = {p.name for p in files if p.parent == root}

    package_path = root / "package.json"
    pyproject_path = root / "pyproject.toml"
    package = _read_json(package_path) if package_path.is_file() else {}
    pyproject = _read_pyproject(pyproject_path) if pyproject_path.is_file() else {}

    name = str(package.get("name") or ((pyproject.get("project") or {}).get("name") if isinstance(pyproject.get("project"), dict) else "") or root.name)
    repository = _git_repository(root)

    language_counts: Counter[str] = Counter()
    module_stats: dict[str, Counter[str]] = {}
    for path in files:
        language = SOURCE_EXTENSIONS.get(path.suffix.lower())
        if not language:
            continue
        language_counts[language] += 1
        rel = path.relative_to(root)
        top = rel.parts[0] if len(rel.parts) > 1 else "."
        module_stats.setdefault(top, Counter())[language] += 1

    package_managers = sorted({label for filename, label in LOCKFILES.items() if filename in root_names})
    if package_path.is_file() and "npm" not in package_managers and not ({"pnpm", "yarn"} & set(package_managers)):
        package_managers.append("npm")

    commands, command_prov, redactions = _commands(root, package, pyproject, root_names)
    env_names, env_sources = _env_names(root)
    frameworks = _frameworks(root, package, pyproject, root_names)

    modules = []
    for module, counts in sorted(module_stats.items(), key=lambda item: (-sum(item[1].values()), item[0]))[:30]:
        modules.append({
            "path": module,
            "source_file_count": sum(counts.values()),
            "language_hints": sorted(counts),
        })

    source_paths: set[Path] = set()
    for name_ in MANIFESTS | set(LOCKFILES):
        p = root / name_
        if p.is_file():
            source_paths.add(p)
    for env_source in env_sources:
        source_paths.add(root / env_source)
    # Provenance of module/language topology: use bounded source metadata, not file contents.
    for p in files:
        if SOURCE_EXTENSIONS.get(p.suffix.lower()) and len(source_paths) < 250:
            source_paths.add(p)
    records = [_source_record(root, p) for p in sorted(source_paths, key=lambda x: _rel(root, x))]
    inventory_fingerprint, source_file_count = _source_inventory(root, files)

    coding = []
    testing = []
    git = []
    convention_sources: list[str] = []
    if (root / "AGENTS.md").is_file():
        coding.append("Follow project AGENTS.md instructions.")
        convention_sources.append("AGENTS.md")
    if (root / "CONTRIBUTING.md").is_file():
        coding.append("Follow CONTRIBUTING.md conventions.")
        convention_sources.append("CONTRIBUTING.md")
    if commands["test"]:
        testing.append("Use discovered project test commands before review.")
    if (root / ".git").exists():
        git.append("Preserve repository history and use task branches/PR delivery.")

    context = {
        "schema_version": "2.1.0",
        "project": {"name": name, "root": str(root), "repository": repository},
        "stack": {
            "languages": [{"name": lang, "file_count": count} for lang, count in language_counts.most_common()],
            "package_managers": package_managers,
            "frameworks": frameworks,
        },
        "modules": modules,
        "architecture": {
            "summary": "",
            "components": [m["path"] for m in modules if m["path"] != "."][:20],
            "boundaries": [],
            "constraints": [],
        },
        "conventions": {"coding": coding, "testing": testing, "git": git},
        "commands": commands,
        "decisions": [],
        "known_risks": [],
        "environment": {"required_variable_names": env_names},
        "provenance": {
            "commands": command_prov,
            "stack": [r["path"] for r in records if Path(r["path"]).name in MANIFESTS or Path(r["path"]).name in LOCKFILES],
            "modules": [r["path"] for r in records if Path(r["path"]).suffix.lower() in SOURCE_EXTENSIONS],
            "conventions": convention_sources,
            "environment": env_sources,
            "redactions": sorted(set(redactions)),
        },
        "discovery": {
            "generated_at": utc_now(),
            "fingerprint": _fingerprint(records),
            "inventory_fingerprint": inventory_fingerprint,
            "source_file_count": source_file_count,
            "sources": records,
            "scan_limit": max_files,
            "files_observed": len(files),
        },
        "updated_at": utc_now(),
    }
    validate_context(context)
    return context


def freshness(project_root: str | Path, context: dict[str, Any]) -> dict[str, Any]:
    root = Path(project_root).resolve()
    context = upgrade_context(context)
    reasons: list[str] = []
    current_records: list[dict[str, Any]] = []
    current_files = list(iter_files(root, max_files=max(context["discovery"].get("scan_limit", 10000), 1)))
    current_inventory, current_source_count = _source_inventory(root, current_files)
    if current_inventory != context["discovery"].get("inventory_fingerprint"):
        reasons.append("source-inventory-changed")
    for record in context["discovery"]["sources"]:
        path = root / record["path"]
        if not path.is_file():
            reasons.append(f"missing:{record['path']}")
            continue
        current = _source_record(root, path)
        current_records.append(current)
        if current != record:
            reasons.append(f"changed:{record['path']}")
    old_paths = {r["path"] for r in context["discovery"]["sources"]}
    # New root manifests are also stale signals even when they were absent before.
    for name in MANIFESTS | set(LOCKFILES) | {".env.example", ".env.sample", ".env.template"}:
        p = root / name
        if p.is_file() and name not in old_paths:
            reasons.append(f"new-source:{name}")
    return {
        "status": "STALE" if reasons else "FRESH",
        "stored_fingerprint": context["discovery"]["fingerprint"],
        "current_fingerprint": _fingerprint(sorted(current_records, key=lambda r: r["path"])),
        "stored_inventory_fingerprint": context["discovery"].get("inventory_fingerprint"),
        "current_inventory_fingerprint": current_inventory,
        "current_source_file_count": current_source_count,
        "reasons": sorted(set(reasons)),
    }


def slice_context(context: dict[str, Any], topics: list[str], *, work_item: str = "") -> dict[str, Any]:
    context = upgrade_context(context)
    allowed = {"stack", "modules", "architecture", "conventions", "commands", "known_risks", "environment"}
    requested = [t for t in topics if t in allowed]
    if not requested:
        raise ProjectScanError(f"no valid topics requested; choose from {sorted(allowed)}")
    result: dict[str, Any] = {
        "schema_version": context["schema_version"],
        "project": context["project"],
        "topics": requested,
        "context": {},
        "provenance": {},
        "source_fingerprint": context["discovery"]["fingerprint"],
    }
    for topic in requested:
        value = context[topic]
        if topic == "modules" and work_item.strip():
            tokens = {x.lower() for x in TOKEN_RE.findall(work_item) if len(x) >= 3}
            ranked = []
            for module in value:
                path_tokens = {x.lower() for x in TOKEN_RE.findall(module["path"])}
                score = len(tokens & path_tokens)
                ranked.append((score, module["path"], module))
            ranked.sort(key=lambda x: (-x[0], x[1]))
            value = [x[2] for x in ranked[:8]]
        result["context"][topic] = value
        prov = context["provenance"].get(topic, [])
        result["provenance"][topic] = prov
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Project Context v2 repository scanner")
    sp = ap.add_subparsers(dest="cmd", required=True)

    p = sp.add_parser("scan")
    p.add_argument("--root", default=".")
    p.add_argument("--max-files", type=int, default=10000)

    p = sp.add_parser("status")
    p.add_argument("--root", default=".")

    p = sp.add_parser("slice")
    p.add_argument("--root", default=".")
    p.add_argument("--topic", action="append", required=True)
    p.add_argument("--work-item", default="")

    args = ap.parse_args()
    try:
        if args.cmd == "scan":
            data = scan_project(args.root, max_files=args.max_files)
            save_context(args.root, data, timestamp=data["updated_at"])
            result = data
        elif args.cmd == "status":
            result = freshness(args.root, load_context(args.root))
        else:
            context = load_context(args.root)
            state = freshness(args.root, context)
            if state["status"] != "FRESH":
                raise ProjectScanError(f"project context is STALE; refresh before use: {state['reasons']}")
            result = slice_context(context, args.topic, work_item=args.work_item)
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    except (ContextStoreError, ProjectScanError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
