import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
ORCHESTRATOR = SCRIPTS / "orchestrator.py"
ROLES = ROOT / "references" / "roles"
REFERENCES = ROOT / "references"

def test_role_context_command_exists_in_orchestrator():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'sp.add_parser("role-context")' in text
    assert 'p.add_argument("--role", required=True' in text
    assert 'elif args.cmd == "role-context":' in text

def test_planner_contract_enforces_role_context():
    text = (ROLES / "planner-contract.md").read_text(encoding="utf-8")
    assert "role-context --role planner" in text
    assert "Do NOT read the full" in text

def test_verifier_contract_enforces_role_context():
    text = (ROLES / "verifier-contract.md").read_text(encoding="utf-8")
    assert "role-context --role verifier" in text
    assert "Do NOT read the full" in text

def test_architect_contract_enforces_role_context():
    text = (REFERENCES / "architect-contract.md").read_text(encoding="utf-8")
    assert "role-context --role architect" in text
    assert "Do NOT read the full" in text

def test_builder_contract_enforces_role_context():
    text = (REFERENCES / "builder-contract.md").read_text(encoding="utf-8")
    assert "role-context --role builder" in text
    assert "Do NOT read the full" in text

def test_skill_md_enforces_role_context():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "role-context --role <role>" in text
    assert "lazy role-scoped context slices" in text

def test_orchestrator_role_context_returns_correct_slice(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import orchestrator as orch

    # Mock the context store and scan to return a dummy context
    dummy_context = {
        "schema_version": "2.1.0",
        "project": {"name": "test"},
        "stack": {},
        "modules": [],
        "architecture": {},
        "conventions": {},
        "commands": {},
        "known_risks": [],
        "environment": {},
        "provenance": {},
        "discovery": {"fingerprint": "abc"}
    }
    monkeypatch.setattr(orch, "load_context", lambda root: dummy_context)
    monkeypatch.setattr(orch, "context_freshness", lambda root, context: {"status": "FRESH"})
    
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'topics = ["architecture", "modules", "stack", "conventions", "known_risks"]' in text  # planner
    assert 'topics = ["architecture", "stack", "known_risks"]' in text  # architect
    assert 'topics = ["modules", "conventions", "environment"]' in text  # builder
    assert 'topics = ["commands", "conventions", "stack"]' in text  # verifier
