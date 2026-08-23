# Orchestrator Contract — MVP 1

The Orchestrator owns routing and lifecycle coordination. It does not replace the Builder, Planner, Verifier, GitHub delivery helpers, external reviewer, or human release authority.

## Responsibilities

- create and resume authoritative v2 tasks under `.ai/tasks/<task-id>/`;
- classify ordinary user requests and route SIMPLE/STANDARD/COMPLEX work;
- require a durable Planner graph for STANDARD/COMPLEX work;
- transition implementation/fix work into the Central Verification Gate;
- allow PR preparation only after verification `PASS` for the candidate SHA;
- reconcile delivery identity before independent review;
- increment review rounds only when beginning a fresh review of a reconciled PR HEAD;
- route `REQUEST_CHANGES`, `APPROVED_TO_MERGE`, and `NEEDS_HUMAN_DECISION` deterministically;
- keep checkpoints and resume state current.

## Non-responsibilities

The Orchestrator must not:

- fabricate GitHub PR state or reviewer results;
- bypass `verification_gate.py`;
- treat an abbreviated or stale SHA as approval evidence;
- claim a dedicated Architect review happened merely because `architect_required=true`;
- auto-merge by default;
- maintain a second authoritative state beside `.ai/tasks/<task-id>/state.json`.

## Review-round ownership

Local implementation retries do not consume external review rounds. A review round increments only when entering `REVIEWING` for a verified candidate whose exact PR HEAD has been reconciled. A new pushed HEAD invalidates previous approval before the next round begins.
