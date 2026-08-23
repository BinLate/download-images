import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"

def test_plan_store_validates_allow_parallelism(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import plan_store
    
    plan = {
        "schema_version": "2.0.0",
        "task_id": "T-20260821-001-test",
        "goal": "g",
        "in_scope": ["a"],
        "out_of_scope": ["a"],
        "constraints": ["a"],
        "assumptions": ["a"],
        "acceptance_criteria": ["a"],
        "risk_level": "LOW",
        "risk_notes": ["a"],
        "release_constraints": ["a"],
        "allow_parallelism": True,
        "work_items": [
            {
                "id": "W1", "owner_role": "BUILDER", "objective": "o",
                "scope_hints": ["src/main.py"], "dependencies": [],
                "verification": ["v"], "status": "PENDING"
            }
        ]
    }
    
    # Should not raise
    plan_store.validate_plan(plan, expected_task_id="T-20260821-001-test")
    
    plan["allow_parallelism"] = "not_a_bool"
    with pytest.raises(plan_store.PlanStoreError):
        plan_store.validate_plan(plan)

def test_sync_task_state_from_plan_parallel_selection(monkeypatch, tmp_path):
    import sys
    sys.path.insert(0, str(SCRIPTS))
    import plan_store
    
    plan = {
        "schema_version": "2.0.0",
        "task_id": "T-20260821-001-test",
        "goal": "g",
        "in_scope": ["a"],
        "out_of_scope": ["a"],
        "constraints": ["a"],
        "assumptions": ["a"],
        "acceptance_criteria": ["a"],
        "risk_level": "LOW",
        "risk_notes": ["a"],
        "release_constraints": ["a"],
        "allow_parallelism": True,
        "work_items": [
            {
                "id": "W1", "owner_role": "BUILDER", "objective": "o",
                "scope_hints": ["src/main.py"], "dependencies": [],
                "verification": ["v"], "status": "READY"
            },
            {
                "id": "W2", "owner_role": "BUILDER", "objective": "o",
                "scope_hints": ["src/utils.py"], "dependencies": [],
                "verification": ["v"], "status": "READY"
            },
            {
                "id": "W3", "owner_role": "BUILDER", "objective": "o",
                "scope_hints": ["src/other.py"], "dependencies": [],
                "verification": ["v"], "status": "READY"
            }
        ]
    }
    
    state = {
        "schema_version": "2.0.0",
        "identity": {"id": "T-20260821-001-test", "original_request": "r", "normalized_title": "t", "created_at": "c", "updated_at": "u"},
        "classification": {"complexity_tier": "STANDARD", "risk_level": "LOW", "kind": "UNKNOWN", "score": 0, "signals": [], "architect_required": False, "planner_required": True, "human_precheck_required": False},
        "requirements": {"goal": "g", "in_scope": [], "out_of_scope": [], "constraints": [], "acceptance_criteria": [], "release_constraints": [], "assumptions": []},
        "plan": {"required": True, "status": "READY", "plan_path": None, "work_item_count": 0, "completed_count": 0, "current_work_item": None, "current_work_items": []},
        "roles": {"active": [], "completed": []},
        "lifecycle": {"current_state": "PLAN_READY", "previous_state": None, "state_entered_at": "c", "transition_reason": "t", "resume_state": None, "local_repair_attempts": 0},
        "implementation": {"branch": None, "candidate_sha": None, "changed_files": [], "work_items_completed": [], "work_items_remaining": []},
        "verification": {"overall_status": "NOT_RUN", "candidate_sha": None, "required_checks": [], "completed_checks": [], "failed_checks": [], "skipped_checks": [], "evidence_ledger_path": "x"},
        "delivery": {"repository": None, "base_branch": None, "head_branch": None, "pr_number": None, "pr_url": None, "pr_state": None, "head_sha": None, "last_push_at": None},
        "review": {"round": 0, "max_rounds": 5, "current_target_sha": None, "current_verdict": None, "current_findings": [], "history_path": "x", "approval_valid": False},
        "decisions": [],
        "blockers": [],
        "release": {"approved_sha": None},
        "checkpoint": None
    }
    
    res = plan_store.sync_task_state_from_plan(state, plan)
    # Should pick W1 and W2 because they are independent and allow_parallelism=True, cap=2
    assert res["plan"]["current_work_items"] == ["W1", "W2"]
    
    # Now let's make W2 overlap with W1
    plan["work_items"][1]["scope_hints"] = ["src/main.py"]
    res2 = plan_store.sync_task_state_from_plan(state, plan)
    # W1 and W2 overlap, so W2 is skipped, W3 is picked!
    assert res2["plan"]["current_work_items"] == ["W1", "W3"]

    # Now let's turn off allow_parallelism
    plan["allow_parallelism"] = False
    res3 = plan_store.sync_task_state_from_plan(state, plan)
    assert res3["plan"]["current_work_items"] == ["W1"]
