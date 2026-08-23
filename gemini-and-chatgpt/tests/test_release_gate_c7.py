import pytest
from pathlib import Path
import json

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"

def test_release_gate_success(monkeypatch, tmp_path):
    import sys
    if str(SCRIPTS) not in sys.path: sys.path.insert(0, str(SCRIPTS))
    import orchestrator
    import task_store
    
    tasks_dir = tmp_path / ".ai" / "tasks"
    tasks_dir.mkdir(parents=True)
    
    task_id = "T-20260821-100-c7"
    task_dir = tasks_dir / task_id
    task_dir.mkdir()
    
    (task_dir / "state.json").write_text(json.dumps({
        "schema_version": task_store.SCHEMA_VERSION,
        "identity": {"id": task_id, "original_request": "r", "normalized_title": "t", "created_at": "c", "updated_at": "u"},
        "classification": {"complexity_tier": "STANDARD", "risk_level": "LOW", "kind": "UNKNOWN", "score": 0, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
        "requirements": {"goal": "g", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": [], "release_constraints": [], "assumptions": []},
        "plan": {"required": True, "status": "READY", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None, "current_work_items": []},
        "roles": {"active": [], "completed": []},
        "lifecycle": {"current_state": "RELEASE_GATE", "previous_state": "REVIEWING", "state_entered_at": "c", "transition_reason": "t", "resume_state": None, "local_repair_attempts": 0},
        "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": []},
        "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": "x"},
        "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": 123, "pr_url": None, "pr_state": None, "head_sha": "a" * 40, "last_push_at": None},
        "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": "x", "approval_valid": True},
        "decisions": [],
        "blockers": [],
        "release": {"approved_sha": "a" * 40, "status": "READY_FOR_HUMAN_RELEASE"},
        "checkpoint": None
    }))
    
    task_store.set_active_task(tmp_path, task_id)
    
    subprocess_called = False
    
    def mock_run(args, **kwargs):
        nonlocal subprocess_called
        subprocess_called = True
        assert args == ["gh", "pr", "merge", "123", "--squash", "--delete-branch"]
        return True
        
    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    state = orchestrator.execute_release(tmp_path, authorize=True)
    
    assert subprocess_called
    assert state["lifecycle"]["current_state"] == "APPROVED"
    assert state["release"]["status"] == "MERGED"

def test_release_gate_requires_authorize(tmp_path):
    import sys
    if str(SCRIPTS) not in sys.path: sys.path.insert(0, str(SCRIPTS))
    import orchestrator
    import task_store
    
    tasks_dir = tmp_path / ".ai" / "tasks"
    tasks_dir.mkdir(parents=True)
    
    task_id = "T-20260821-100-c7"
    task_dir = tasks_dir / task_id
    task_dir.mkdir()
    
    (task_dir / "state.json").write_text(json.dumps({
        "schema_version": task_store.SCHEMA_VERSION,
        "identity": {"id": task_id, "original_request": "r", "normalized_title": "t", "created_at": "c", "updated_at": "u"},
        "classification": {"complexity_tier": "STANDARD", "risk_level": "LOW", "kind": "UNKNOWN", "score": 0, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
        "requirements": {"goal": "g", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": [], "release_constraints": [], "assumptions": []},
        "plan": {"required": True, "status": "READY", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None, "current_work_items": []},
        "roles": {"active": [], "completed": []},
        "lifecycle": {"current_state": "RELEASE_GATE", "previous_state": "REVIEWING", "state_entered_at": "c", "transition_reason": "t", "resume_state": None, "local_repair_attempts": 0},
        "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": []},
        "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": "x"},
        "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": 123, "pr_url": None, "pr_state": None, "head_sha": "a" * 40, "last_push_at": None},
        "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": "x", "approval_valid": True},
        "decisions": [],
        "blockers": [],
        "release": {"approved_sha": "a" * 40, "status": "READY_FOR_HUMAN_RELEASE"},
        "checkpoint": None
    }))
    
    task_store.set_active_task(tmp_path, task_id)
    
    with pytest.raises(orchestrator.OrchestratorError, match="explicit --authorize flag is required"):
        orchestrator.execute_release(tmp_path, authorize=False)
