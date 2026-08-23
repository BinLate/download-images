#!/usr/bin/env python3
"""Durable C1 Architect decision artifact for gemini-and-chatgpt MVP 2."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any

class ArchitectError(RuntimeError): pass
REQUIRED = {"summary","drivers","decisions","interfaces","constraints","risks","builder_guidance","verification_implications"}

def architecture_path(root: str|Path, task_id: str) -> Path:
    return Path(root)/".ai"/"tasks"/task_id/"architecture.json"

def validate_architecture(data: dict[str,Any], task_id: str|None=None) -> None:
    if not isinstance(data, dict): raise ArchitectError("architecture artifact must be an object")
    if data.get("schema_version") != "1.0.0": raise ArchitectError("architecture schema_version must be 1.0.0")
    if task_id and data.get("task_id") != task_id: raise ArchitectError("architecture task_id mismatch")
    if data.get("status") != "READY": raise ArchitectError("architecture status must be READY")
    decision = data.get("decision")
    if not isinstance(decision, dict) or set(decision) != REQUIRED: raise ArchitectError(f"decision fields must be exactly {sorted(REQUIRED)}")
    if not isinstance(decision["summary"], str) or not decision["summary"].strip(): raise ArchitectError("decision.summary is required")
    for key in REQUIRED-{"summary"}:
        if not isinstance(decision[key], list): raise ArchitectError(f"decision.{key} must be an array")
    if data.get("production_code_edits") not in (False, None): raise ArchitectError("Architect must not edit production code in C1")
    if not isinstance(data.get("human_precheck_required"), bool): raise ArchitectError("human_precheck_required must be boolean")

def save_architecture(root: str|Path, data: dict[str,Any], task_id: str) -> Path:
    validate_architecture(data, task_id)
    p=architecture_path(root, task_id); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return p

def load_architecture(root: str|Path, task_id: str) -> dict[str,Any]:
    p=architecture_path(root, task_id)
    if not p.exists(): raise ArchitectError(f"architecture artifact not found: {p}")
    data=json.loads(p.read_text(encoding="utf-8")); validate_architecture(data, task_id); return data

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest="cmd", required=True)
    p=sp.add_parser("validate"); p.add_argument("--root",default="."); p.add_argument("--task-id",required=True)
    p=sp.add_parser("save"); p.add_argument("--root",default="."); p.add_argument("--task-id",required=True); p.add_argument("--input",required=True)
    a=ap.parse_args()
    try:
        if a.cmd=="save":
            d=json.loads(Path(a.input).read_text(encoding="utf-8")); print(save_architecture(a.root,d,a.task_id))
        else: print(json.dumps(load_architecture(a.root,a.task_id),indent=2,ensure_ascii=False))
    except (OSError,json.JSONDecodeError,ArchitectError) as e: raise SystemExit(str(e))
if __name__=="__main__": main()
