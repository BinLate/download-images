# gemini-and-chatgpt v2 — MVP 1 Implementation Backlog

Date: 2026-08-19  
Canonical source: `My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt`  
Source basis:
- `docs/architecture-current.md`
- `docs/architecture-awf.md`
- `docs/integration-matrix.md`
- `docs/architecture-v2.md`

Status: **MVP 1 implementation complete through B8 on 2026-08-19. Deterministic/internal exit gates pass; external Windows installer execution and real GitHub PR + ChatGPT Web review remain environment validation requirements before a production-release claim.**

Implementation checkpoint — Step 06:

- `B0 Baseline + regression harness`: **COMPLETE** — 21 regression/schema tests pass.
- `B1 Schemas + storage contracts`: **COMPLETE** — 5 Draft 2020-12 schemas added and meta-validated.
- Runtime scripts `workflow_state.py`, `pr_context.py`, and `parse_review.py`: **UNCHANGED**.
- GitHub PR creation/reviewer round: **NOT EXECUTED in this runtime** because GitHub CLI `gh` is unavailable and outbound GitHub DNS/network access failed. Canonical Google Drive source has been updated directly; do not interpret this checkpoint as a merged GitHub PR.
- Next implementation batch: **B2 — State machine, task store, context store, checkpoints, migration foundation**.

Implementation checkpoint — Step 08:

- `B0 Baseline + regression harness`: **COMPLETE**.
- `B1 Schemas + storage contracts`: **COMPLETE**.
- `B2 State machine + task/context/checkpoint stores`: **COMPLETE**.
- `B3 Task classifier/risk router`: **COMPLETE** — deterministic taxonomy, complexity/risk routing, hard triggers and Planner/Architect/human-precheck flags implemented.
- `B4 Planner task graph`: **COMPLETE** — authoritative `plan.json`, deterministic `plan.md`, DAG/cycle checks, dependency-aware readiness and task-state synchronization implemented.
- Regression suite: **61 tests pass**; all 5 schemas pass Draft 2020-12 meta-validation; Python helpers pass `py_compile`.
- Runtime compatibility: v1 delivery/review path remains active. B3+B4 do not activate Verification Gate B5, orchestrator B6, or dedicated Architect execution.
- GitHub PR creation/reviewer round: **NOT EXECUTED in this runtime** because GitHub CLI `gh` is unavailable here. Canonical Google Drive source is updated directly; do not interpret this checkpoint as a merged/reviewed GitHub PR.
- Next implementation batch: **B5 — Central Verification Gate + evidence ledger**.

Implementation checkpoint — Step 09:

- `B0 Baseline + regression harness`: **COMPLETE**.
- `B1 Schemas + storage contracts`: **COMPLETE**.
- `B2 State machine + task/context/checkpoint stores`: **COMPLETE**.
- `B3 Task classifier/risk router`: **COMPLETE**.
- `B4 Planner task graph`: **COMPLETE**.
- `B5 Central Verification Gate + evidence ledger`: **COMPLETE** — exact-candidate-SHA evidence, append-only ledger, required-check fail-closed aggregation, and task-state verification summary implemented.
- Regression suite: **76 tests pass**; Python helpers pass `py_compile`; Verification Gate CLI integration smoke passes.
- Runtime compatibility: B5 does not yet activate the v2 orchestrator. `workflow_state.py`, `pr_context.py`, `parse_review.py` and the current delivery/review path remain available.
- GitHub PR creation/reviewer round: **NOT EXECUTED in this runtime** because GitHub CLI `gh` is unavailable here. Canonical Google Drive source is updated directly; this checkpoint is not a GitHub review/merge claim.
- Next implementation batch: **B6 — Orchestrator + compatibility integration**.



Implementation checkpoint — Step 10:

- `B0` through `B5`: **COMPLETE**.
- `B6 Orchestrator + compatibility integration`: **COMPLETE** — v2 init/classify/plan/implementation/verification/delivery/review routing implemented in `scripts/orchestrator.py`.
- `workflow_state.py`: **COMPATIBILITY FACADE** — delegates/projects active v2 task state when present; preserves legacy `.ai/review-state.json` behavior otherwise.
- Review-round ownership: increment occurs only on `PR_PREPARING -> REVIEWING` for a reconciled exact PR HEAD; local fix/verification retries do not consume rounds.
- Delivery guard: PR HEAD must exactly equal the Verification Gate candidate SHA before review entry.
- Release behavior: `APPROVED_TO_MERGE` routes to `RELEASE_GATE` with `merge_policy=human_only`; no auto-merge.
- Regression suite: **89 tests pass**; all 5 schemas pass Draft 2020-12 meta-validation; Python helpers pass `py_compile`.
- GitHub PR creation/reviewer round: **NOT EXECUTED in this runtime** because GitHub CLI `gh` is unavailable here. B6 reuses the existing GitHub/ChatGPT backend but cannot exercise it end-to-end in this environment.
- Next implementation batch: **B7 — exact-SHA review/delivery hardening + reviewer prompt enrichment**.

Implementation checkpoint — Step 11:

- `B0` through `B6`: **COMPLETE**.
- `B7 Review/delivery exact-SHA hardening`: **COMPLETE** — parser and delivery identity now require exact full 40-character SHAs; abbreviated/prefix equivalence is rejected.
- `pr_context.py`: requires PR state `OPEN`, validates full local/PR/base SHAs, and invalidates stale approval on HEAD change while retargeting `current_target_sha` to the new HEAD.
- `review_prompt.py`: projects task identity/scope, acceptance criteria, material constraints, implementation/changed-file context, exact PR identity, SHA-bound verification evidence, prior findings/dispositions, and the full reviewer contract; it does not dump project memory/chat history.
- Review policy: fresh ChatGPT Web conversation is required for every round; old approval has no authority after a changed HEAD.
- Release policy: `human_only` remains the default; no auto-merge.
- Regression suite: **100 tests pass** in timeout-safe groups; all Python helpers pass `py_compile`; schema tests remain green.
- GitHub PR creation/reviewer round: **NOT EXECUTED in this runtime** because GitHub CLI `gh` is unavailable here. Canonical Drive source is updated directly; this is not a GitHub review/merge claim.
- Next implementation batch: **B8 — activation, installer, documentation, and full MVP E2E exit gate**.

Implementation checkpoint — Step 12:

- `B0` through `B7`: **COMPLETE**.
- `B8 Activation + installer + documentation`: **COMPLETE** — natural-language activation is encoded in `SKILL.md` and one managed project-root `AGENTS.md` block; the installer clean-refreshes one project-local skill, copies schemas, validates required v2 files, and retains explicit `(default Y)` behavior.
- `B8 deterministic/internal MVP E2E gate`: **PASS** — approval path stops at `RELEASE_GATE`; `REQUEST_CHANGES` creates a new candidate and fresh review round; wrong SHA cannot release.
- Reconstructed working-copy regression: **64/64 PASS**, including **9/9 B8-focused tests**; Python helpers pass `py_compile`. Prior canonical full B0-B7 checkpoint remains **100 tests PASS**.
- Installer file-format/static checks: DOS BAT with CRLF, balanced parenthesis count, schemas included, automatic merge OFF.
- External Windows BAT/PowerShell execution: **NOT EXECUTED** — this runtime has no `cmd.exe`, Windows PowerShell, or `pwsh`.
- Real GitHub PR -> fresh ChatGPT Web reviewer E2E: **NOT EXECUTED** — GitHub CLI `gh` is unavailable in this runtime.
- MVP exit-gate conclusion: **IMPLEMENTATION COMPLETE / INTERNAL GATE PASS / EXTERNAL ENVIRONMENT VALIDATION REQUIRED**. Do not describe the unavailable external checks as passing.

## 1. MVP 1 objective

MVP 1 adds the AWF-derived front-half capabilities to the existing `gemini-and-chatgpt` delivery/review loop without replacing the proven GitHub/HEAD/ChatGPT Web back-half.

MVP 1 must deliver:

1. authoritative per-task state under `.ai/tasks/<task-id>/`;
2. deterministic legal state transitions;
3. a task classifier with `SIMPLE`, `STANDARD`, and `COMPLEX` output;
4. durable machine-readable plans for non-trivial tasks;
5. a minimal project context store;
6. deterministic checkpoints/resume;
7. one centralized Verification Gate with an append-only evidence ledger;
8. orchestration that preserves the current branch → push → PR → exact HEAD SHA → ChatGPT Web loop;
9. exact full-SHA reviewer validation;
10. reviewer prompts enriched with task acceptance criteria and verification evidence;
11. compatibility with the existing `.ai/review-state.json` workflow during migration;
12. updated `SKILL.md`, role/policy references, README/install documentation, and activation rules.

MVP 1 is complete only if ordinary user coding requests still require no slash command and the current independent ChatGPT Web release boundary remains intact.

## 2. Explicit non-goals for MVP 1

The following are intentionally deferred:

- real parallel/multi-process agents;
- dedicated Architect execution as a separate AI invocation;
- Designer/UI persona;
- AWF-style `/brainstorm`, `/customize`, adaptive-language, or named personas;
- global AWF installation or `.brain/`;
- background/message-count auto-save;
- semantic search across long-term context;
- automatic deployment;
- automatic merge;
- self-update;
- Cloudflare tunnel workflows;
- advanced coverage policy;
- generic autonomous creation of ad-hoc tests when no meaningful test strategy exists.

`COMPLEX` tasks are still detected in MVP 1. Hard-risk triggers set `architect_required` and/or `human_precheck_required`; until the dedicated Architect role is implemented later, the orchestrator must fail safely into the existing human/planning gate instead of pretending architecture review occurred.

## 3. Implementation strategy

Use **incremental replacement with compatibility**, not a big-bang rewrite.

The existing delivery/review path remains usable throughout migration:

```text
Builder
  -> local verification
  -> Git branch / commit / push
  -> PR
  -> exact PR HEAD SHA
  -> fresh ChatGPT Web review
  -> parse verdict
  -> fix / reverify / repush / fresh review
  -> human release gate
```

New v2 components are introduced ahead of and around this path. Existing scripts remain available until their replacement has regression evidence.

Core rule:

> No batch may delete or bypass an existing P0 review invariant before the replacement passes its regression gate.

## 4. Dependency graph

```text
B0 Baseline + regression harness
 |
 v
B1 Schemas + storage contracts
 |
 v
B2 State machine + task/context/checkpoint stores
 |
 +------------------+
 |                  |
 v                  v
B3 Classifier     B4 Planning / plan store
 |                  |
 +--------+---------+
          |
          v
B5 Verification Gate + evidence ledger
          |
          v
B6 Orchestrator integration + v1 compatibility
          |
          v
B7 Review/delivery hardening + prompt enrichment
          |
          v
B8 Activation, installer, docs, E2E exit gate
```

`B3` and `B4` may be developed in parallel after `B2`, but they should merge before `B5/B6`.

## 5. Backlog summary

| Batch | Priority | Main result | Risk | Depends on |
|---|---:|---|---|---|
| B0 | P0 | Freeze current invariants and add regression harness | Low | — |
| B1 | P0 | Add v2 JSON schemas | Low | B0 |
| B2 | P0 | Authoritative task state, legal transitions, context/checkpoints | High | B1 |
| B3 | P1 | Task classifier/risk router | Medium | B2 |
| B4 | P1 | Machine plan store + human Markdown projection | Medium | B2 |
| B5 | P1 | Central Verification Gate + evidence ledger | High | B3, B4 |
| B6 | P0/P1 | Orchestrator connects v2 front-half to existing backend | Highest | B5 |
| B7 | P0 | Full exact-SHA hardening + reviewer prompt integration | High | B6 |
| B8 | P0/P1 | Activation/install/docs/E2E migration exit gate | High | B7 |

## 6. Batch B0 — Baseline and regression harness

### Purpose

Before changing state semantics, freeze the behavior that must never regress.

### Files

Create:

```text
tests/
├── test_workflow_state_v1.py
├── test_pr_context.py
├── test_parse_review.py
└── fixtures/
    ├── review-approved.txt
    ├── review-request-changes.txt
    ├── review-malformed.txt
    └── review-wrong-sha.txt
```

Do not change runtime behavior in this batch except tiny testability refactors that preserve outputs.

### Required regression assertions

- v1 workflow state can initialize/show/set/increment review round;
- malformed review output fails closed;
- unsupported verdict fails closed;
- expected SHA mismatch is rejected;
- `pr_context.py` rejects local HEAD != PR HEAD;
- review round default remains 5;
- auto-merge remains off by policy;
- ordinary task activation contract is still represented in `SKILL.md`.

### Test framework

Prefer Python standard-library `unittest` unless the repository already has a justified test dependency. Do not add a Python package solely to run these helper-script tests.

### Exit gate

All baseline tests pass against the current implementation.

### Suggested commit

`test: freeze v1 review-loop invariants`

## 7. Batch B1 — V2 schemas and data contracts

### Purpose

Define machine contracts before writing orchestration logic.

### Files

Create:

```text
schemas/
├── project-context.schema.json
├── task-state.schema.json
├── plan.schema.json
├── verification-evidence.schema.json
└── checkpoint.schema.json
```

Create schema tests:

```text
tests/
└── test_schemas.py
```

### Required schema rules

#### `project-context.schema.json`

Must support:

- project/repository identity;
- architecture summary/boundaries/constraints;
- coding/testing/git conventions;
- install/lint/typecheck/test/build commands;
- decisions;
- known risks;
- required environment variable **names only**;
- `updated_at`;
- explicit schema version.

Must reject or provide no field intended for secret values.

#### `task-state.schema.json`

Must contain domains for:

- identity;
- classification;
- requirements;
- plan;
- roles;
- lifecycle;
- implementation;
- verification;
- delivery;
- review;
- decisions;
- blockers;
- release;
- checkpoint metadata.

#### `plan.schema.json`

Must represent:

- task identity;
- goal;
- acceptance criteria;
- risk;
- work items;
- dependencies;
- owner role;
- verification requirements;
- work-item status;
- release constraints.

#### `verification-evidence.schema.json`

Each evidence record must support at minimum:

- task id;
- candidate SHA;
- command/check identity;
- check category;
- started/completed timestamps;
- exit code or normalized status;
- concise result summary;
- relevant scope;
- whether the check was required;
- skip/failure reason when applicable.

#### `checkpoint.schema.json`

Must capture enough state to resume safely while never storing credentials/secrets.

### Exit gate

- valid examples pass;
- missing required fields fail;
- invalid enums fail;
- secret-value fixture is rejected or demonstrably outside the schema contract.

### Suggested commit

`feat: define v2 workflow schemas`

## 8. Batch B2 — State machine, task store, context store, checkpoints

### Purpose

Create the deterministic foundation. This is the first critical runtime batch.

### Files

Create:

```text
scripts/
├── state_machine.py
├── context_store.py
├── task_store.py
└── migrate_state.py
```

Update later, but do not remove yet:

```text
scripts/workflow_state.py
```

Create tests:

```text
tests/
├── test_state_machine.py
├── test_task_store.py
├── test_context_store.py
├── test_checkpoints.py
└── test_migrate_state.py
```

### State machine

Initial states:

```text
RECEIVED
CLASSIFIED
PLANNING
PLAN_READY
IMPLEMENTING
VERIFYING
PR_PREPARING
REVIEWING
FIXING
RELEASE_GATE
APPROVED
BLOCKED
HUMAN_DECISION
REVIEW_LIMIT_REACHED
FAILED
ABORTED
```

Required legal transition examples:

```text
RECEIVED -> CLASSIFIED

CLASSIFIED -> IMPLEMENTING
CLASSIFIED -> PLANNING
CLASSIFIED -> HUMAN_DECISION

PLANNING -> PLAN_READY
PLANNING -> BLOCKED
PLANNING -> HUMAN_DECISION

PLAN_READY -> IMPLEMENTING

IMPLEMENTING -> VERIFYING
IMPLEMENTING -> BLOCKED
IMPLEMENTING -> FAILED

VERIFYING -> IMPLEMENTING       # local repair
VERIFYING -> PR_PREPARING
VERIFYING -> BLOCKED
VERIFYING -> FAILED

PR_PREPARING -> REVIEWING
PR_PREPARING -> BLOCKED
PR_PREPARING -> FAILED

REVIEWING -> FIXING
REVIEWING -> RELEASE_GATE
REVIEWING -> HUMAN_DECISION
REVIEWING -> REVIEW_LIMIT_REACHED

FIXING -> VERIFYING

RELEASE_GATE -> APPROVED
RELEASE_GATE -> HUMAN_DECISION

BLOCKED -> <recorded resume_state only>
```

Direct illegal jumps such as `IMPLEMENTING -> REVIEWING` and `FIXING -> REVIEWING` must fail.

### Task storage

Authoritative path:

```text
.ai/
├── active-task.json
└── tasks/<task-id>/
    ├── state.json
    └── checkpoints/
```

Requirements:

- atomic writes where practical;
- stable filesystem-safe task IDs;
- timestamps;
- schema version;
- one authoritative active task pointer;
- stale/corrupt state fails closed;
- checkpoint written at deterministic transitions;
- no raw chat transcript persistence.

### Project context

Initial MVP scope is intentionally small:

- repository identity;
- stable architecture/convention notes;
- discovered/confirmed verification commands;
- durable user/project constraints;
- environment variable names.

Do not attempt automatic full-codebase memory extraction in MVP 1.

### V1 migration

`migrate_state.py` must support importing useful fields from `.ai/review-state.json` into the active v2 task state.

Important:

- preserve PR number/URL/base/head SHA;
- preserve review round/max rounds;
- preserve current verdict when trustworthy;
- recompute current Git/PR identity before resuming review;
- never treat migrated stale SHA as authoritative without reconciliation.

### Exit gate

- all legal/illegal transition tests pass;
- checkpoint restore works;
- corrupted state does not silently reset into a dangerous state;
- migration fixture preserves review identity;
- existing v1 scripts still run.

### Suggested commit

`feat: add authoritative v2 task state machine`

## 9. Batch B3 — Task classifier and risk router

### Purpose

Make planning proportional instead of forcing every task through the same ceremony.

### Files

Create:

```text
scripts/task_classifier.py
tests/test_task_classifier.py
```

### Initial output

```json
{
  "kind": "BUGFIX|FEATURE|REFACTOR|DOCS|CONFIG_BUILD|TEST|DEPENDENCY|SECURITY|ARCHITECTURE|MAINTENANCE|UNKNOWN",
  "complexity_tier": "SIMPLE|STANDARD|COMPLEX",
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "score": 0,
  "signals": [],
  "planner_required": false,
  "architect_required": false,
  "human_precheck_required": false
}
```

### Hard triggers

At minimum flag:

- DB/schema/data migration;
- public/breaking API;
- authentication/authorization/security;
- production infrastructure;
- destructive data operation;
- significant concurrency/data-integrity impact;
- major dependency migration;
- broad cross-service architecture.

### MVP behavior

- `SIMPLE`: create minimal task contract and route to implementation.
- `STANDARD`: planner required.
- `COMPLEX`: planner required; set `architect_required`; hard-risk tasks may also set `human_precheck_required`.

Dedicated Architect execution is deferred. MVP 1 must not claim architectural approval occurred merely because `architect_required=true`.

### Exit gate

Fixture set covers at least:

- typo/docs edit;
- one-file bug;
- multi-file bug;
- ordinary feature;
- DB migration;
- auth change;
- dependency major upgrade;
- broad refactor;
- ambiguous unknown task.

### Suggested commit

`feat: add task complexity and risk classifier`

## 10. Batch B4 — Planner contract and plan store

### Purpose

Add durable task decomposition without importing AWF slash-command UX.

### Files

Create:

```text
scripts/plan_store.py
references/roles/planner-contract.md
schemas/plan.schema.json        # already created in B1; refine only compatibly
tests/test_plan_store.py
```

Optionally create generated plan template logic inside `plan_store.py`; do not add fixed AWF web-app phase templates.

### Planner output contract

For `STANDARD`/`COMPLEX` tasks the Planner must produce:

- normalized goal;
- in-scope/out-of-scope;
- constraints;
- assumptions;
- acceptance criteria;
- work-item graph;
- dependencies;
- verification requirement per work item;
- release constraints;
- risk notes.

### Storage

```text
.ai/tasks/<task-id>/
├── plan.json    # authority
└── plan.md      # generated human-readable view
```

Rules:

- `plan.json` is authoritative;
- Markdown cannot silently mutate machine state;
- simple tasks may omit full `plan.json` but still have normalized requirements in `state.json`;
- work items use stable IDs;
- dependency cycles are rejected;
- ready work items are derived from dependencies.

### Exit gate

- valid graph saves/loads;
- cycle detection fails closed;
- Markdown projection is deterministic enough for review;
- task state progress reflects plan state;
- no hard-coded “database/backend/frontend” phase sequence.

### Suggested commit

`feat: add durable planner task graph`

## 11. Batch B5 — Central Verification Gate

### Purpose

Replace duplicated ad-hoc QA semantics with one deterministic gate.

### Files

Create:

```text
scripts/verification_gate.py
references/roles/verifier-contract.md
references/policies/verification-policy.md
tests/test_verification_gate.py
```

### Evidence path

```text
.ai/tasks/<task-id>/verification.jsonl
```

Append-only records are preferred so prior evidence is not silently rewritten.

### MVP check categories

```text
LINT
TYPECHECK
FOCUSED_TEST
REGRESSION_TEST
BUILD
INTEGRATION_SMOKE
CUSTOM
```

### Policy

The gate receives:

- task classification/risk;
- task/plan verification requirements;
- project-context known commands;
- candidate commit SHA;
- project capabilities.

It outputs:

```text
PASS
FAIL
BLOCKED
PARTIAL
```

`PASS` is required before `PR_PREPARING`.

`PARTIAL` cannot silently become PASS. It either requires a documented policy exception/human decision or additional checks.

### Candidate identity rule

Verification evidence must bind to the candidate commit SHA intended for delivery. If code changes after verification, the evidence for the old SHA cannot automatically validate the new candidate.

### Repair loop

Local verification repair is bounded separately from the external five-round ChatGPT review loop.

Suggested default:

- up to 3 local repair attempts for the same verification failure class;
- after that: `BLOCKED` or `HUMAN_DECISION` depending on reason.

### Exit gate

- passing command produces PASS evidence;
- failing command produces FAIL;
- missing mandatory command produces BLOCKED/PARTIAL as policy specifies;
- skipped required check cannot result in unconditional PASS;
- evidence records bind to candidate SHA;
- modified candidate invalidates prior verification status.

### Suggested commit

`feat: add centralized verification gate`

## 12. Batch B6 — Orchestrator and compatibility integration

### Purpose

Connect the new front-half to the existing GitHub/review back-half.

This is the highest-risk MVP batch.

### Files

Create:

```text
scripts/orchestrator.py
references/roles/orchestrator-contract.md
references/roles/delivery-contract.md
```

Update:

```text
scripts/workflow_state.py
references/workflow.md
```

### Orchestrator responsibilities

- initialize/resume active task;
- classify;
- choose SIMPLE vs STANDARD/COMPLEX route;
- call planning contract when required;
- enforce state transitions;
- create checkpoints;
- drive implementation/verification phase boundaries;
- stop when human precheck is required;
- enter delivery only after Verification PASS;
- preserve external review round counters;
- set terminal states.

### Compatibility strategy

`workflow_state.py` becomes a compatibility wrapper:

- if v2 active task exists, delegate to v2 state;
- if only legacy `.ai/review-state.json` exists, preserve legacy behavior and offer/perform migration according to command contract;
- do not maintain two divergent authoritative states.

### Delivery boundary

MVP 1 should reuse the proven pieces rather than rewrite them:

- `pr_context.py`;
- GitHub CLI lifecycle described in existing workflow;
- `copy_review_prompt.ps1`;
- current ChatGPT Web interaction model;
- current finding dispositions;
- current human gate.

### Exit gate

E2E dry/fixture scenarios:

1. SIMPLE task -> IMPLEMENTING -> VERIFYING -> PR_PREPARING.
2. STANDARD task -> PLANNING -> PLAN_READY -> IMPLEMENTING.
3. COMPLEX hard-risk task -> human precheck, no silent implementation.
4. Verification fail -> local repair path.
5. Illegal transition attempt rejected.
6. Resume from checkpoint continues from reconciled state.
7. Legacy review state can resume without loss of PR identity.

### Suggested commit

`feat: integrate v2 orchestrator with legacy delivery loop`

## 13. Batch B7 — Review and delivery hardening

### Purpose

Upgrade the existing back-half only where v2 requires stronger identity/evidence.

### Files

Update:

```text
scripts/parse_review.py
scripts/pr_context.py
references/review-contract.md
```

Create:

```text
scripts/review_prompt.py
references/policies/review-policy.md
references/policies/safety-release-policy.md
tests/test_review_prompt.py
tests/test_review_exact_sha.py
```

### Exact SHA rule

Change reviewer SHA validation to:

- exactly 40 hexadecimal characters;
- case-insensitive normalized comparison if desired;
- exact equality with the current expected full SHA;
- no 7-character or prefix equivalence.

Malformed/missing/stale SHA -> `NEEDS_HUMAN_DECISION` or fail-closed parser error according to the command contract.

### Reviewer prompt projection

The prompt builder should include only relevant review data:

- task ID/title;
- goal and in/out scope;
- acceptance criteria;
- material assumptions/constraints;
- implementation summary;
- changed-file/diff context;
- PR identity;
- exact full target HEAD SHA;
- verification evidence summary bound to that SHA;
- prior blocking findings/resolution summary for rounds >1;
- full reviewer contract.

Do not dump the entire project context or conversation history.

### Approval invalidation

Whenever a new HEAD is pushed:

```text
approval_valid = false
current_verdict = null
current_target_sha = new_head
```

A previous `APPROVED_TO_MERGE` must never survive a code-changing push.

### Exit gate

- old SHA approval rejected after new HEAD;
- abbreviated SHA rejected;
- exact full SHA accepted;
- prompt contains acceptance criteria + QA evidence;
- prompt excludes known secret fields;
- review round 5 boundary still enforced;
- fresh-chat-per-round policy remains documented.

### Suggested commit

`fix: harden exact-sha review identity`

## 14. Batch B8 — Activation, installer, documentation, and MVP exit gate

### Purpose

Expose v2 as one product only after runtime foundations pass.

### Files

Update:

```text
SKILL.md
README.md
references/installation.md
references/workflow.md
scripts/install_agents_rule.ps1
INSTALL-ANTIGRAVITY.bat
agents/openai.yaml
```

Add if the canonical source uses a changelog:

```text
CHANGELOG.md
```

If no canonical changelog exists, do not fabricate history; create one only when deliberately adopting it as a v2 repository convention.

### SKILL.md changes

Move from a long monolithic procedural document toward:

- invariant summary;
- natural-language auto-activation;
- entry to orchestrator;
- role/policy references;
- human/release boundary;
- browser constraints.

Do not duplicate all deterministic state-machine logic in prose.

### `AGENTS.md` installation rule

Installed workspace rule should instruct Antigravity to:

1. recognize ordinary coding work;
2. enter the v2 orchestrator;
3. preserve no-skill-name UX;
4. use existing review backend;
5. stop on human-required conditions.

### Installer rules

Before changing `INSTALL-ANTIGRAVITY.bat`:

- inspect current canonical installer content/provenance;
- retain current Git/GitHub onboarding behavior unless deliberately changed;
- preserve `(default Y)` and `(default N)`;
- pressing Enter must select the displayed default;
- review all `if (...)` blocks and parentheses/escaping carefully;
- make reruns idempotent;
- do not install AWF as a second framework.

### README

Present one product:

```text
copy gemini-and-chatgpt into project
-> run INSTALL-ANTIGRAVITY.bat
-> open project in Antigravity
-> give a normal coding task
```

Document SIMPLE/STANDARD/COMPLEX routing conceptually without requiring user commands.

### MVP 1 E2E scenario matrix

The exit suite must include at least:

1. simple docs/typo task;
2. small bugfix;
3. multi-file bugfix;
4. ordinary feature;
5. complex/schema task;
6. auth/security hard trigger;
7. verification command failure;
8. verification repair success;
9. local repair limit reached;
10. PR creation/update path;
11. local HEAD != PR HEAD;
12. malformed reviewer output;
13. abbreviated reviewer SHA;
14. exact reviewer SHA;
15. REQUEST_CHANGES round 1;
16. REQUEST_CHANGES with valid fix and new SHA;
17. stale approval after push;
18. round 5 without approval;
19. human gate;
20. interrupted session + resume;
21. corrupted task state;
22. legacy `.ai/review-state.json` migration;
23. installer first run;
24. installer rerun/idempotency.

### Final MVP regression gate

MVP 1 cannot be declared complete unless:

- all v2 unit/integration tests pass;
- old review-loop regression tests pass;
- no code path can review without an exact current PR HEAD;
- no code path can push a fix and skip re-verification;
- no code path can carry approval across a changed HEAD;
- no code path can exceed review round 5 automatically;
- no code path auto-merges by default;
- migration/resume does not silently trust stale GitHub identity;
- normal user tasks still auto-activate without `/plan`, `/code`, or skill name;
- installer rerun does not create duplicate/conflicting activation rules.

### Suggested commit

`docs: activate and document v2 mvp workflow`

## 15. Recommended merge/PR sequence

Do not put MVP 1 into one giant PR.

Recommended implementation PRs:

```text
PR-1  B0 + B1
      Baseline tests + schemas

PR-2  B2
      Task state machine + storage + migration foundation

PR-3  B3 + B4
      Classifier + planning/task graph

PR-4  B5
      Verification Gate

PR-5  B6
      Orchestrator + compatibility bridge

PR-6  B7
      Review/delivery exact-SHA hardening

PR-7  B8
      Activation + installer + docs + full E2E gate
```

Every PR must pass the existing independent ChatGPT Web review loop before it is considered ready to merge. Do not use unfinished v2 behavior to waive the existing review gate while v2 is being built.

## 16. Per-PR regression checklist

Run after every implementation PR:

```text
[ ] Python helper syntax/import tests
[ ] New unit tests for touched subsystem
[ ] Existing v1 regression suite
[ ] No secret values persisted
[ ] No illegal state transition introduced
[ ] GitHub PR identity behavior unchanged unless explicitly in B7
[ ] Exact-current-HEAD review remains mandatory
[ ] Review round max remains 5
[ ] Auto-merge remains off
[ ] AGENTS auto-activation unchanged unless intentionally in B8
[ ] README/contract changes match runtime behavior
```

For PRs B6-B8 also run the relevant E2E fixture scenarios.

## 17. Rollback strategy

Each batch must be independently reversible.

Rules:

- schemas are additive before readers depend on them;
- legacy scripts are retained through B6/B7;
- `review-state.json` compatibility is removed only in a later post-MVP migration, not MVP 1;
- do not rename/remove existing files in the same commit that introduces their replacement unless compatibility has already been proven;
- state migrations create a backup/checkpoint before rewriting;
- installer changes are last, after runtime is stable.

If B6 orchestrator integration fails, rollback to the existing `SKILL.md`-driven review loop while retaining isolated schemas/tests that do not affect runtime.

## 18. Definition of Done — MVP 1

A normal user can install the tool once and then say a coding request naturally.

For a SIMPLE task:

```text
task -> classify -> implement -> verify -> PR -> exact SHA -> ChatGPT review
```

For a STANDARD task:

```text
task -> classify -> durable plan -> implement -> verify -> PR -> exact SHA -> ChatGPT review
```

For a COMPLEX/high-risk task:

```text
task -> classify -> durable plan/risk state -> human/architecture precheck when required
```

For reviewer changes:

```text
REQUEST_CHANGES
-> Builder validates finding
-> fix
-> candidate commit
-> Verification Gate
-> push
-> new exact SHA
-> fresh ChatGPT review
```

And the system must still stop at:

```text
APPROVED_TO_MERGE -> RELEASE_GATE -> APPROVED -> STOP
```

with merge remaining human-controlled by default.

## 19. Post-MVP backlog boundary

After MVP 1 is stable, the next architecture increments may add:

- dedicated conditional Architect role execution;
- richer Project Context discovery;
- topic-based lazy context retrieval;
- snapshot retention/recovery policies;
- Designer/UI role;
- project-health scanner;
- controlled parallel work-item execution;
- optional personalization/adaptive language;
- deployment workflows;
- updater/version migration tooling.

These must not delay MVP 1.

## 20. Implementation start point

The first coding work should be **B0 + B1 only**.

Reason:

- no orchestration behavior changes;
- gives a regression safety net;
- fixes data contracts before runtime code is written;
- creates the lowest-risk first PR;
- provides the foundation needed to implement B2 correctly.

**Step 05 gate:** COMPLETE when this backlog is accepted as the implementation order. Coding begins only in the next step.

## Implementation checkpoint — Step 13

- External validation checklist: **CREATED** in `docs/external-mvp-validation-checklist.md`.
- Current-runtime preflight: `git 2.47.3` available; working copy is not a Git repository; `gh`, `cmd.exe`, Windows PowerShell/`pwsh`, interactive Antigravity, and an authenticated controllable ChatGPT Web reviewer session are unavailable.
- Internal regression re-run: **64/64 PASS**; B8-focused activation/installer + internal E2E: **9/9 PASS**; Python `py_compile`: **PASS**.
- External validation verdict: **EXTERNAL_MVP_VALIDATION_BLOCKED**. No unavailable Windows/GitHub/ChatGPT Web check is represented as passing.
- Required next environment: Windows workstation with Antigravity, Git, authenticated GitHub CLI, a disposable GitHub repository, and an authenticated ChatGPT Web browser session.

Implementation checkpoint — Post-Step 13 clipboard transport hardening:

- External validation exposed a real clipboard race: unrelated user clipboard activity between clipboard preparation and browser paste could replace the reviewer prompt; simulated typing also risked accidental partial submission on Enter.
- FIXED: `review_prompt.py` now repeats deterministic `PROMPT_ID` + exact full `TARGET_HEAD_SHA` at both transport boundaries.
- FIXED: `copy_review_prompt.ps1` requires exact clipboard read-back equality before browser insertion.
- FIXED: new `verify_review_transport.py` deterministically compares the full composer read-back against `reviewer-prompt.txt` after newline normalization and validates transport identity before Send.
- FAIL-CLOSED: clipboard replacement, truncation/partial submission, changed middle content, wrong `PROMPT_ID`, and wrong HEAD are regression-tested and rejected. Mismatch path is `clear -> recopy -> reinsert -> reread -> reverify`, at most 3 attempts, then stop.
- POLICY: simulated character-by-character typing is disabled by default and is not an automatic fallback. If full composer read-back is unavailable, do not Send.
- REGRESSION: **76/76 PASS** plus Python `py_compile` PASS in the current working copy.
- External Gate E must be re-run after reinstalling/refreshing the project-local skill before final external validation can continue.


Implementation checkpoint — Post-Step 13 paste-target integrity hardening:

- External Gate E exposed a second browser transport race: after unrelated clipboard activity, global keyboard focus could land in Chrome's address bar rather than the ChatGPT composer, causing a pasted URL to navigate away when Enter was later issued.
- FIXED: new `verify_review_target.py` requires the expected fresh ChatGPT reviewer URL, `document.hasFocus() == true`, visible/enabled composer, recognized composer metadata, and `document.activeElement === composer` before insertion.
- FIXED: the same target guard runs again immediately before Send, so URL/focus drift after insertion cannot authorize submission.
- POLICY: prefer direct DOM/field fill. `Ctrl+V` is permitted only with uninterrupted verified composer focus and no intervening user/tool yield; otherwise fail closed. No Enter is allowed as part of bulk prompt transport.
- REGRESSION: address-bar focus, body/other-element focus, changed/copied conversation URL, wrong host, hidden/disabled composer, and unknown selector all fail closed.
- External Gate E must be re-run after refreshing the project-local skill. Current external verdict remains blocked until the corrected live browser path is validated.


Implementation checkpoint — Gate E runtime observability hotfix:

- Added append-only `review-runtime.jsonl` plus bounded `review-runtime-state.json` via `scripts/review_runtime_log.py`.
- Default hard limits: Gate E 900s overall, normal browser phase 120s, reviewer-response wait 300s, transport attempts 3.
- Every browser/transport phase must log start/result and check limits before retry/wait. Timeout or attempt-limit is `BLOCKED`; infinite browser loops are forbidden.
- This hotfix is diagnostic/operational only and does not weaken exact-SHA, target-focus, transport, independent-review, or human-release invariants.

### Post-MVP external-validation hotfix — reviewer language/private repo (2026-08-20)

Status: COMPLETE and externally re-reviewed.

- Reviewer channel is English-only while user-facing Antigravity communication remains in the user's language.
- Private GitHub PR browser access is no longer an approval prerequisite after the deterministic delivery gate has reconciled OPEN PR + exact full HEAD and the review package contains the SHA-bound diff/context/evidence.
- `NEEDS_HUMAN_DECISION` remains required for actual identity inconsistency, materially insufficient evidence, or another substantive blocker.
- Focused reviewer-prompt regression: 6/6 PASS. Available reconstructed regression suite: 66/66 PASS. `py_compile` PASS.


### Transport hardening follow-up — completed

Implemented direct-fill-first reviewer transport and atomic clipboard fallback (`reviewer-prompt.txt` -> arm -> immediate paste). The fallback deliberately removes clipboard read-back before paste to minimize the user clipboard race window while preserving post-paste full composer verification and exact target verification before Send.

### Post-MVP hardening — attachment-aware reviewer transport (2026-08-20)
- [x] Add `verify_review_attachments.py` and fail closed when prompt text is correct but an image/file attachment is present.
- [x] Require attachment checks after insertion and immediately before Send.
- [x] Add regression for screenshot clipboard race.
- [x] Re-run the final transport smoke test externally after installer refresh — PASS.


## MVP 1 external exit gate — CLOSED

Status: `EXTERNAL_MVP_VALIDATION_PASS` (2026-08-20).

The Windows Antigravity external validation reached `RELEASE_GATE` on exact PR HEAD `c726754cd00e970b879864894c7d6820d8b1604f` with `APPROVED_TO_MERGE`, stopped before merge under `human_only`, and the final post-Gate-G transport hardening passed a negative screenshot/attachment smoke test. MVP 1 external exit criteria are therefore closed.


## Step 14 checkpoint — MVP 2 planning

- MVP 1 external exit gate: `EXTERNAL_MVP_VALIDATION_PASS`.
- MVP 2 roadmap created in `docs/mvp2-roadmap.md`.
- Recommended sequence: C1 Architect -> C2 Project Context v2 -> C3 role-scoped context -> C5 QA scanner -> C4 controlled parallel execution -> C6 recovery/migrations -> MVP 2 E2E.
- First implementation increment: **C1 Dedicated Architect role only**.


## MVP 2 — C1 checkpoint (2026-08-20)

Status: COMPLETE / EXTERNAL VALIDATION PASS. C1 validated SIMPLE Architect bypass, COMPLEX `architect_required=true` activation, Architect -> Builder ordering, durable `architecture.json`, production-code-edit rejection, high-risk `HUMAN_DECISION`, exact-SHA review, and stop at `RELEASE_GATE`. Post-validation hardening forbids GitHub-Web-only PR verification for private repos and forbids self-validation from modifying source/installed Skill folders. C2 may start.


## MVP 2 — C2 checkpoint (2026-08-20)

Status: IMPLEMENTED / INTERNAL REGRESSION PASS. Added `project_context_scan.py`, Project Context schema 2.1.0, provenance/fingerprint freshness checks, lazy topic slicing, legacy 2.0 compatibility upgrade, secret-safe env-name discovery, and automatic context refresh for non-trivial classification/resume. C3 must not start until C2 regression and external smoke/exact-SHA review pass.

### Post-MVP hardening — shared clipboard retry race v2 (2026-08-20)
- [x] Reproduced user-copy race where unrelated text could be pasted repeatedly because browser retry reused the shared clipboard.
- [x] Add `paste_review_prompt.ps1` to perform source-file validation -> clipboard set -> exact read-back -> Windows clipboard-sequence check -> immediate Ctrl+V in one process.
- [x] Make direct DOM/field fill the primary path and guarded single-process paste the only automatic clipboard fallback.
- [x] Require every retry to clear the draft, reverify composer focus, and re-arm from `reviewer-prompt.txt`; never reuse current clipboard contents.
- [x] Add foreign-payload circuit breaker: the same unrelated payload twice, or 3 total attempts, stops `BLOCKED` instead of looping.
- [x] Keep composer readback, attachment guard, exact target check, timeout and human-only release policy unchanged.


### Post-C2 transport hardening — clipboard-free reviewer transport (2026-08-20)
- External smoke tests reproduced repeated foreign clipboard insertion despite guarded paste helpers.
- Decision: remove Windows clipboard from active reviewer transport.
- New priority: direct DOM/field fill -> controlled typed fallback from `reviewer-prompt.txt` -> BLOCKED.
- Typed fallback forbids Ctrl+V and plain Enter; Shift+Enter is allowed only for explicit newline key events when required by the browser primitive.
- Existing exact text readback, PROMPT_ID/TARGET_HEAD_SHA binding, attachment guards, timeouts, and human-only release gate remain unchanged.


### Transport hardening checkpoint — line-safe typed fallback (2026-08-20)
- Added deterministic `typed_review_plan.py` after external smoke testing showed browser typing APIs may map embedded newlines to plain Enter/submission.
- Fallback now types one line per action and inserts source newlines only with Shift+Enter; clipboard remains fully disabled.

- 2026-08-20 transport source-integrity hotfix: added immutable `reviewer-prompt.manifest.json` (SHA256/chars/lines/PROMPT_ID/HEAD/full-package structure), `review_package_guard.py`, fail-closed typed/transport verification, and prohibition on smoke tests overwriting the real reviewer package. Regression includes the observed false-PASS case where only three marker/identity lines were left in the composer.


### Transport hotfix — real DIRECT_FILL_CDP (2026-08-20)
- Added `scripts/direct_fill_review_prompt.ps1`.
- Uses Chrome DevTools Protocol `Input.insertText` for one-shot full multiline prompt insertion without clipboard or Enter key events.
- Requires immutable package guard, exact ChatGPT composer focus, empty draft, and full composer readback verification.
- Falls back to line-safe typed transport only when no usable Antigravity Chrome DevTools endpoint is exposed.


### Transport performance hotfix — one-shot DIRECT_FILL send (2026-08-20)
- [x] Collapse normal reviewer transport into one PowerShell/CDP helper call.
- [x] Verify immutable manifest/hash/line count, exact composer target, empty draft, and zero attachments internally.
- [x] Insert full prompt with `Input.insertText`, exact-readback verify, then click Send automatically.
- [x] Remove redundant Python verifier chain from successful DIRECT_FILL_CDP happy path.
- [x] Keep standalone verifiers for diagnostics/fallback/regression only.
- [x] Reserve `-NoSend` for explicit smoke tests; normal flow must send.
- [x] Prevent long retry loops: only exit code 3 permits typed fallback; other failures stop `BLOCKED`.


### Transport redesign — dedicated reviewer browser + single-command review round (2026-08-21)
- [x] Remove normal dependency on the Antigravity-owned Chrome DevTools endpoint.
- [x] Launch/reuse a dedicated persistent Chrome reviewer profile with a known CDP TCP port.
- [x] Remove automatic typed fallback from normal reviewer transport.
- [x] Add `scripts/review_round.py` to consolidate PR reconciliation -> immutable package -> DIRECT_FILL -> attachment/readback verification -> Send -> response wait -> parse -> lifecycle transition.
- [x] Store reviewer artifacts under `.ai/tasks/<task-id>/reviews/round-XX/` instead of project root.
- [x] Keep one-time reviewer login as an explicit resumable condition; all other transport failures fail closed.


## 2026-08-21 — Runtime command-count + reviewer-browser attach-first hotfix

- Added `orchestrator.py start` to combine task initialization and classification/routing.
- `orchestrator.py verify` now auto-binds IMPLEMENTING/FIXING candidates before running the Verification Gate, removing the normal `begin-verify` call.
- Normal SIMPLE path explicitly ignores GitHub/ChatGPT/workflow infrastructure when estimating product scope; one-file low-risk work bypasses Planner/Project Context.
- Added in-process `.ai/gemini-chatgpt-actions.log` + `.jsonl` with action/command/status/duration; logging does not spawn helper processes.
- Reviewer transport now prefers an already-running Antigravity Chrome CDP endpoint. Dedicated reviewer Chrome is fallback only when no existing debuggable Chrome is available.
- Fixed the PowerShell 5.1 one-item pipeline unboxing bug that could turn the Chrome executable path into the single character `C`.
- Normal happy path forbids helper `--help`, repeated reassurance state checks, standalone reviewer verifiers, and typed/clipboard transport.
- External Windows live validation remains required before declaring this hotfix complete.


### Reviewer transport efficiency hardening — single-tab / no full-round retry (2026-08-21)

- [x] Diagnose action log: repeated full `review_round.py` invocations were the dominant wasted work; the successful final round itself completed in tens of seconds.
- [x] Remove redundant `gh repo view` and `gh pr diff` from review happy path; use one `gh pr view`, local HEAD check, and local exact base...head `git diff`.
- [x] Stop Antigravity from manually opening/clicking ChatGPT before `review_round.py`.
- [x] Persist and reuse one reviewer tab; create a new tab only when no reusable ChatGPT target exists.
- [x] Freshen each round by direct `Page.navigate` to `https://chatgpt.com/`, not by clicking `New chat`.
- [x] Remove keyboard-selection recovery. Stale composer state is cleared through DOM state only.
- [x] On readback mismatch, allow exactly one in-place clear+reinsert inside the same transport invocation; never restart the full review round automatically.
- [x] Log reviewer-target reuse, composer reset count, insertion attempts, Send, response, and duration to the existing action log.
