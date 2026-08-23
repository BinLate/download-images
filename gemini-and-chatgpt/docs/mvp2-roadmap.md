# Gemini + ChatGPT v2 — MVP 2 Roadmap

Date: 2026-08-20
Status: C1 COMPLETE / C2 INTERNAL PASS / EXTERNAL VALIDATION NEXT
Baseline: MVP 1 external validation PASS
Canonical source: `My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt`

## 1. MVP 2 goal

Evolve the validated MVP 1 workflow into a practical AI software team without stacking another framework on top of it.

Preserve the proven control plane:

```text
User task
-> Antigravity/Gemini orchestration
-> deterministic planning/state/evidence
-> GitHub branch + PR + exact HEAD SHA
-> independent ChatGPT Web review
-> fix/review loop
-> human-only RELEASE_GATE
```

MVP 2 adds deeper role specialization, project-aware context, and controlled parallel execution while keeping one authoritative state machine and one delivery/review gate.

## 2. Non-goals

MVP 2 will NOT:

- add a second orchestration framework beside gemini-and-chatgpt;
- replace GitHub PR + exact-SHA review with conversational trust;
- allow agents to merge automatically by default;
- allow uncontrolled recursive agent spawning;
- make every task use every persona;
- require global AWF installation;
- duplicate authoritative state stores;
- add deployment automation before core multi-agent behavior is stable.

## 3. Architecture principle

Roles are capabilities selected by the orchestrator, not independent frameworks.

```text
Orchestrator
├── Planner
├── Architect        # conditional
├── Builder          # one or more controlled work items
├── Verifier / QA
└── Reviewer         # ChatGPT Web, independent
```

The orchestrator remains the only owner of lifecycle transitions. Roles may propose outputs but may not independently advance release authority.

## 4. MVP 2 work packages

### C1 — Dedicated Architect role

Purpose: activate an Architect only when classifier/risk/planner signals justify it.

Deliverables:
- `architect_required` becomes executable routing rather than metadata only;
- `references/architect-contract.md`;
- architecture decision artifact under `.ai/tasks/<task-id>/architecture.md` or structured equivalent;
- Architect cannot edit production code directly by default;
- high-risk architectural decisions can require human precheck;
- regression for SIMPLE task bypass and COMPLEX task activation.

Exit gate:
- SIMPLE tasks do not pay Architect overhead;
- architecture-sensitive tasks produce a durable decision before Builder execution.

### C2 — Project Context v2

Purpose: give agents durable project knowledge without dumping the repository or chat history into every prompt.

Deliverables:
- repository discovery scanner;
- structured project context: stack, commands, test/build entrypoints, key modules, constraints, conventions;
- source provenance and freshness metadata;
- lazy loading by topic/work item;
- stale-context invalidation rules;
- no secrets copied into context artifacts.

Exit gate:
- a fresh session can resume a task with enough project knowledge to work safely without broad repository re-analysis.

### C3 — Role-scoped context retrieval

Purpose: each role receives only the context it needs.

Examples:
- Planner: goals, constraints, dependency map;
- Architect: boundaries, interfaces, architecture history;
- Builder: assigned work item + relevant files/contracts;
- Verifier: candidate SHA + acceptance criteria + test commands;
- Reviewer: exact-SHA diff/evidence package only.

Exit gate:
- deterministic tests prove unrelated context is excluded from role packages.

### C4 — Controlled multi-work-item execution

Purpose: allow limited parallelism without losing ownership or creating merge chaos.

Rules:
- parallelism is opt-in from Planner graph;
- only dependency-independent work items can run concurrently;
- default concurrency cap: 2;
- each work item has explicit file/module ownership hints;
- overlapping write scope forces serialization or replan;
- all outputs converge to one candidate commit/branch before Verification Gate;
- no independent agent PRs in MVP 2.

Exit gate:
- two independent work items can complete safely and converge into one verified candidate;
- conflict/overlap is detected before destructive parallel edits.

### C5 — Project Health / QA scanner

Purpose: improve verification selection before review.

Deliverables:
- detect available lint/typecheck/test/build commands from project context;
- classify required vs optional checks;
- detect missing test coverage for changed areas when practical;
- feed only deterministic evidence into the existing Verification Gate;
- never silently downgrade a failing required check.

Exit gate:
- verifier chooses appropriate checks without manually hardcoding every project command.

### C6 — Recovery, retention, and migration hardening

Purpose: make the AI team safe for long-running real projects.

Deliverables:
- checkpoint retention policy;
- old task/archive cleanup policy;
- schema/version migration hooks;
- deterministic resume after interrupted multi-agent execution;
- updater/version compatibility strategy for project-local installs.

Exit gate:
- interrupted task resumes without duplicate agent work, stale approval, or state ambiguity.

## 5. Explicitly deferred after MVP 2

Defer until C1-C6 are externally validated:

- Designer/UI specialist role;
- deployment/release automation;
- concurrency above 2;
- autonomous sub-agent spawning trees;
- cross-repository orchestration;
- adaptive personalization beyond language/preferences;
- automatic merge.

## 6. Recommended implementation order

```text
C1 Architect routing
-> C2 Project Context v2
-> C3 Role-scoped context
-> C5 Project Health / QA scanner
-> C4 Controlled parallel execution
-> C6 Recovery + migrations
-> internal MVP 2 E2E
-> Windows external MVP 2 validation
```

Why C4 comes after C5: parallel builders should not be introduced until context isolation and deterministic verification are already stable.

## 7. PR strategy

Use small PRs with the existing exact-SHA reviewer loop:

- PR-M2-1: C1 Architect role
- PR-M2-2: C2 Project Context v2
- PR-M2-3: C3 role-scoped context
- PR-M2-4: C5 project-health / QA scanner
- PR-M2-5: C4 controlled parallel execution
- PR-M2-6: C6 recovery/migration hardening
- PR-M2-7: MVP 2 internal + external exit-gate docs/tests

Each PR must preserve v1 compatibility unless explicitly removed in a separately approved migration.

## 8. MVP 2 success criteria

MVP 2 is complete only when all are true:

1. Architect activation is conditional and deterministic.
2. Persistent project context is structured, provenance-aware, lazy, and secret-safe.
3. Role prompts receive scoped context rather than full project dumps.
4. At least two dependency-independent work items can execute under controlled concurrency and converge safely.
5. Verification commands are selected from project context and remain exact-SHA bound.
6. ChatGPT Web remains the independent reviewer; reviewer authority is still exact-SHA bound.
7. REQUEST_CHANGES invalidates prior approval and triggers reverify + fresh review as in MVP 1.
8. Workflow still stops at `RELEASE_GATE`; merge remains `human_only` by default.
9. Recovery after interruption does not duplicate work or revive stale evidence.
10. Windows Antigravity external MVP 2 validation passes.

## 9. First implementation step

Start with **C1 only**.

C1 is intentionally narrow: convert the existing `architect_required` signal into a real conditional Architect execution path, add its contract/artifact, integrate it with Planner/orchestrator state, and test that SIMPLE tasks bypass it.

Do not begin C2-C6 until C1 regression and exact-SHA review pass.

## C1 implementation checkpoint — 2026-08-20

C1 is implemented and internally regression-tested. Conditional Architect routing now activates only when `architect_required=true`; SIMPLE tasks bypass it. Required architecture decisions are durable in `.ai/tasks/<task-id>/architecture.json`, Builder execution fails closed until the artifact is READY, and Architect can escalate to `HUMAN_DECISION`. Next gate is exact-SHA review of C1 before starting C2.


## 10. C1 completion

C1 Dedicated Architect passed Windows/Antigravity external validation on 2026-08-20. The validated path covered SIMPLE bypass, COMPLEX Architect activation, durable architecture artifact, Builder blocking before architecture readiness, no direct production edits, high-risk human routing, exact-SHA independent review, and human-only `RELEASE_GATE`.

Post-validation safeguards: use `gh` + `pr_context.py` rather than GitHub Web for private-PR identity, and keep both source/installed Skill copies immutable during self-validation. Next work package: **C2 Project Context v2**.


## 11. C2 implementation checkpoint

C2 implementation adds bounded repository discovery, Project Context schema 2.1.0, stack/command/module summaries, provenance and SHA-256 freshness fingerprinting, lazy topic slices, secret-safe environment-name handling, and automatic refresh for planned/architectural work and recovery. Internal regression and a Windows/Antigravity exact-SHA smoke are required before C3 begins.

## 12. C3 implementation checkpoint

C3 Role-scoped Context Retrieval is implemented and regression-tested. The `orchestrator.py role-context` command now deterministically bounds topic slices based on the requesting role (`planner`, `architect`, `builder`, `verifier`). Role contracts and `SKILL.md` strictly prohibit full `.ai/project-context.json` retrieval. Next work package: **C5 Project Health / QA scanner**.

## 13. C5 implementation checkpoint

C5 Project Health / QA Scanner is implemented and regression-tested. The `project_health_scanner.py` parses `.ai/project-context.json` to automatically resolve lint, typecheck, test, and build commands into deterministic checks. The `orchestrator.py verify` command defaults to these checks if none are explicitly provided, streamlining the Verifier role. Next work package: **C4 Controlled parallel execution**.

## 14. C4 implementation checkpoint

C4 Controlled Multi-work-item Execution is implemented and regression-tested. The `plan.json` schema now supports `allow_parallelism`. The `plan_store.py` state synchronization enforces a maximum concurrency of 2 and statically prevents concurrent execution of work items with overlapping `scope_hints`. Outputs converge to a single candidate commit as required. Next work package: **C6 Recovery, retention, and migration hardening**.

## 15. C6 implementation checkpoint

C6 Recovery, retention, and migration hardening is implemented and tested. Checkpoint pruning ensures only the 5 most recent checkpoints are retained. The `orchestrator.py cleanup` command sweeps terminal tasks older than 7 days into an archive directory. A seamless `migrate_state` hook automatically handles schema version upgrades (e.g. populating `current_work_items`). Next work package: **Final E2E Release Gate and Integration Validation**.

## 16. Final E2E Release Gate and Integration Validation

C7 Final E2E Release Gate is implemented and tested. The `orchestrator.py release` subcommand allows merging a verified release candidate safely with a mandatory `--authorize` flag. It executes a `gh pr merge` and safely transitions the task state from `RELEASE_GATE` to the final `APPROVED` terminal state.

**All MVP 2 Roadmap Deliverables are fully implemented and complete!**
