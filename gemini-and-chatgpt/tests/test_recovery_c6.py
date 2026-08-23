import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta
import json
import shutil

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"

def test_checkpoint_cleanup(tmp_path):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import task_store
    
    # Create mock checkpoints
    task_id = "T-20260821-001-test"
    cp_dir = tmp_path / ".ai" / "tasks" / task_id / "checkpoints"
    cp_dir.mkdir(parents=True, exist_ok=True)
    
    for i in range(10):
        f = cp_dir / f"2026082100000{i}Z-STATE.json"
        f.write_text("{}")
        
    removed = task_store.cleanup_checkpoints(tmp_path, task_id, keep=3)
    assert removed == 7
    remaining = list(cp_dir.iterdir())
    assert len(remaining) == 3
    assert "20260821000009Z-STATE.json" in [r.name for r in remaining]

def test_schema_migration():
    import sys
    if str(SCRIPTS) not in sys.path: sys.path.insert(0, str(SCRIPTS))
    import task_store
    
    # Pre-C4 state with no current_work_items
    old_state = {
        "schema_version": "1.0.0",
        "plan": {
            "current_work_item": "W1"
        }
    }
    
    migrated = task_store.migrate_state(old_state)
    assert migrated["schema_version"] == task_store.SCHEMA_VERSION
    assert migrated["plan"]["current_work_items"] == ["W1"]

def test_archive_completed_tasks(monkeypatch, tmp_path):
    import sys
    if str(SCRIPTS) not in sys.path: sys.path.insert(0, str(SCRIPTS))
    import task_store
    
    tasks_dir = tmp_path / ".ai" / "tasks"
    tasks_dir.mkdir(parents=True)
    
    # Mock utc_now to be a specific date
    now = datetime(2026, 8, 21, tzinfo=timezone.utc)
    monkeypatch.setattr(task_store, "utc_now", lambda: "2026-08-21T00:00:00Z")
    
    # Create an old RELEASED task (8 days old)
    task1 = tasks_dir / "T-20260810-001-old"
    task1.mkdir()
    (task1 / "state.json").write_text(json.dumps({
        "schema_version": task_store.SCHEMA_VERSION,
        "identity": {"id": "T-20260810-001-old", "original_request": "r", "normalized_title": "t", "created_at": "c", "updated_at": "2026-08-13T00:00:00Z"},
        "classification": {"complexity_tier": "STANDARD", "risk_level": "LOW", "kind": "UNKNOWN", "score": 0, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
        "requirements": {"goal": "g", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": [], "release_constraints": [], "assumptions": []},
        "plan": {"required": True, "status": "READY", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None, "current_work_items": []},
        "roles": {"active": [], "completed": []},
        "lifecycle": {"current_state": "APPROVED", "previous_state": None, "state_entered_at": "c", "transition_reason": "t", "resume_state": None, "local_repair_attempts": 0},
        "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": []},
        "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": "x"},
        "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": None, "pr_url": None, "pr_state": None, "head_sha": None, "last_push_at": None},
        "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": "x", "approval_valid": False},
        "decisions": [],
        "blockers": [],
        "release": {"approved_sha": None},
        "checkpoint": None
    }))

    # Create a recent RELEASED task (2 days old)
    task2 = tasks_dir / "T-20260819-001-new"
    task2.mkdir()
    (task2 / "state.json").write_text(json.dumps({
        "schema_version": task_store.SCHEMA_VERSION,
        "identity": {"id": "T-20260819-001-new", "original_request": "r", "normalized_title": "t", "created_at": "c", "updated_at": "2026-08-19T00:00:00Z"},
        "classification": {"complexity_tier": "STANDARD", "risk_level": "LOW", "kind": "UNKNOWN", "score": 0, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
        "requirements": {"goal": "g", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": [], "release_constraints": [], "assumptions": []},
        "plan": {"required": True, "status": "READY", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None, "current_work_items": []},
        "roles": {"active": [], "completed": []},
        "lifecycle": {"current_state": "APPROVED", "previous_state": None, "state_entered_at": "c", "transition_reason": "t", "resume_state": None, "local_repair_attempts": 0},
        "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": []},
        "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": "x"},
        "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": None, "pr_url": None, "pr_state": None, "head_sha": None, "last_push_at": None},
        "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": "x", "approval_valid": False},
        "decisions": [],
        "blockers": [],
        "release": {"approved_sha": None},
        "checkpoint": None
    }))

    # Create an old IMPLEMENTING task (should NOT be archived)
    task3 = tasks_dir / "T-20260810-002-active"
    task3.mkdir()
    (task3 / "state.json").write_text(json.dumps({
        "schema_version": task_store.SCHEMA_VERSION,
        "identity": {"id": "T-20260810-002-active", "original_request": "r", "normalized_title": "t", "created_at": "c", "updated_at": "2026-08-10T00:00:00Z"},
        "classification": {"complexity_tier": "STANDARD", "risk_level": "LOW", "kind": "UNKNOWN", "score": 0, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
        "requirements": {"goal": "g", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": [], "release_constraints": [], "assumptions": []},
        "plan": {"required": True, "status": "READY", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None, "current_work_items": []},
        "roles": {"active": [], "completed": []},
        "lifecycle": {"current_state": "IMPLEMENTING", "previous_state": None, "state_entered_at": "c", "transition_reason": "t", "resume_state": None, "local_repair_attempts": 0},
        "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": []},
        "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": "x"},
        "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": None, "pr_url": None, "pr_state": None, "head_sha": None, "last_push_at": None},
        "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": "x", "approval_valid": False},
        "decisions": [],
        "blockers": [],
        "release": {"approved_sha": None},
        "checkpoint": None
    }))

    archived = task_store.archive_completed_tasks(tmp_path)
    assert archived == 1
    
    assert not task1.exists()
    assert (tasks_dir / "archive" / "T-20260810-001-old").exists()
    
    assert task2.exists()
    assert task3.exists()
