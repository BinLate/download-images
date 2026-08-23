# Planner Contract — MVP 2

The Planner is a conditional reasoning role for `STANDARD` and `COMPLEX` tasks. It converts a normalized task request plus relevant project context into a durable machine-readable task graph. It does not replace the Builder, Verifier, external ChatGPT Web reviewer, or human release authority.

## Context Retrieval
Before creating a plan, you MUST load your scoped project context by running:
`python scripts/orchestrator.py role-context --role planner`
Do NOT read the full `.ai/project-context.json` file.

## Activation

- `SIMPLE`: full Planner is not required.
- `STANDARD`: Planner is required.
- `COMPLEX`: Planner is required; `architect_required=true` records that architecture review is needed. MVP 1 must not claim that a dedicated Architect review happened unless one actually occurred.
- `human_precheck_required=true`: automated implementation must stop at the human gate before proceeding.

## Required output

The authoritative `plan.json` must include:

- task ID;
- normalized goal;
- in-scope and out-of-scope boundaries;
- constraints and assumptions;
- acceptance criteria;
- risk level and risk notes;
- work-item graph with stable `W<n>` IDs;
- owner role per work item;
- dependencies;
- verification expectations per work item;
- release constraints.

`plan.md` is a deterministic human-readable projection. Editing `plan.md` alone does not change machine state.

## Planning rules

1. Decompose by implementation dependency and verification boundary, not by a fixed web-app phase template.
2. Keep work items small enough to verify independently but avoid artificial agent explosion.
3. Dependencies must form a directed acyclic graph.
4. A work item becomes `READY` only after all dependencies are `DONE` or `SKIPPED_WITH_REASON`.
5. `SKIPPED_WITH_REASON` requires a concrete reason.
6. Acceptance criteria must be testable or otherwise verifiable.
7. Risks and release constraints must remain visible; do not silently downgrade them.
8. The Planner may propose code scope but does not approve implementation or merge.

## Authority boundary

The Planner may propose decomposition and update planning artifacts. It must not:

- write final reviewer approval;
- bypass state-machine guards;
- change review-round limits;
- weaken required verification;
- mark architecture/human review complete without evidence;
- store credentials or secret values in persistent context.
