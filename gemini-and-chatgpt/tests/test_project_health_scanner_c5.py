import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
HEALTH_SCANNER = SCRIPTS / "project_health_scanner.py"
ORCHESTRATOR = SCRIPTS / "orchestrator.py"

def test_project_health_scanner_exists():
    assert HEALTH_SCANNER.exists()
    text = HEALTH_SCANNER.read_text(encoding="utf-8")
    assert "scan_health(" in text
    assert "commands_dict.get(kind, [])" in text

def test_orchestrator_supports_qa_scan():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    assert 'sp.add_parser("qa-scan")' in text
    assert 'elif args.cmd == "qa-scan":' in text
    assert 'from project_health_scanner import scan_health' in text

def test_orchestrator_verify_optional_checks():
    text = ORCHESTRATOR.read_text(encoding="utf-8")
    # ensure checks is optional
    assert 'p.add_argument("--checks", default="")' in text
    # ensure it falls back to scan_health
    assert 'if not checks:' in text
    assert 'checks = scan_health(args.root)' in text

def test_scan_health_mapping(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import project_health_scanner as scanner
    import context_store

    dummy_context = {
        "schema_version": "2.1.0",
        "commands": {
            "lint": ["flake8"],
            "test": ["pytest"],
            "build": ["npm run build"]
        }
    }
    
    monkeypatch.setattr(scanner, "load_context", lambda root: dummy_context)
    monkeypatch.setattr(scanner, "context_freshness", lambda root, context: {"status": "FRESH"})
    
    checks = scanner.scan_health(tmp_path)
    
    # expected order: lint, typecheck (none), test, build
    assert len(checks) == 3
    assert checks[0]["id"] == "lint"
    assert checks[0]["command"] == "flake8"
    assert checks[0]["required"] is True
    
    assert checks[1]["id"] == "test"
    assert checks[1]["command"] == "pytest"
    assert checks[1]["required"] is True

    assert checks[2]["id"] == "build"
    assert checks[2]["command"] == "npm run build"
    assert checks[2]["required"] is True

