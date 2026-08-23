# gemini-and-chatgpt v2 — Unified Target Architecture

Date: 2026-08-19
Canonical source: `My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt`
Status: Architecture design only. No runtime integration is authorized by this document alone.

Source basis:
- `docs/architecture-current.md`
- `docs/architecture-awf.md`
- `docs/integration-matrix.md`

## 1. Architecture decision

`gemini-and-chatgpt v2` is one unified Antigravity software-engineering system. It evolves from the existing `gemini-and-chatgpt` delivery/review protocol and selectively internalizes the strongest AWF concepts.

It is NOT:

- AWF installed next to `gemini-and-chatgpt`;
- a chain of mandatory slash commands;
- a collection of named personas pretending to be independent agents;
- a second `.brain/` state tree beside `.ai/`;
- a fully autonomous multi-process agent swarm;
- an automatic merge/deployment system.

It IS:

- natural-language task intake;
- complexity-aware planning;
- formal role/authority contracts;
- deterministic state transitions;
- durable project/task context;
- one centralized verification policy;
- GitHub PR + exact HEAD SHA delivery identity;
- independent ChatGPT Web review;
- bounded repair/re-review loops;
- explicit human release/safety authority.

The core design principle is:

```text
AI reasons.
Deterministic components enforce state, identity, evidence, and gates.
GitHub identifies what is being reviewed.
ChatGPT Web independently reviews that exact code.
Human authority is never bypassed.
```

## 2. Non-negotiable invariants

1. Users submit ordinary coding requests; explicit skill names or slash commands are not required.
2. Workspace rules may auto-activate the unified workflow.
3. Antigravity/Gemini is the implementation authority.
4. ChatGPT Web is an external independent reviewer, never an internal Gemini persona.
5. Final independent review requires an open/current GitHub PR.
6. Each review is bound to the exact full current PR HEAD SHA.
7. Any new pushed HEAD invalidates the previous review verdict/approval.
8. Reviewer output is parsed fail-closed.
9. Builder evaluates findings using evidence; it does not blindly obey the reviewer.
10. Accepted fixes must pass the Verification Gate before push/re-review.
11. External review remains capped at 5 rounds by default.
12. `APPROVED_TO_MERGE` stops before merge unless merge policy is explicitly changed by the user.
13. Human-required conditions cannot be bypassed by an AI role.
14. There is one installer and one activation model.
15. Persistent project state never stores secret values.

## 3. Logical architecture

```text
User natural-language task
        |
        v
+----------------------------+
| Activation / Task Intake   |
+----------------------------+
        |
        v
+----------------------------+
| Classifier / Risk Router   |
+----------------------------+
        |
        +---------- SIMPLE -----------------------------+
        |                                               |
        |                                               v
        |                                      Minimal task contract
        |
        +---------- STANDARD / COMPLEX -----------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | Planning Layer              |
                                      | Planner                     |
                                      | Architect (conditional)     |
                                      | Task graph + acceptance     |
                                      +-----------------------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | Context / State Layer       |
                                      | authoritative task state    |
                                      | project context             |
                                      | checkpoints                 |
                                      +-----------------------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | Builder                     |
                                      | Antigravity / Gemini        |
                                      +-----------------------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | Candidate Commit            |
                                      +-----------------------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | Verification Gate           |
                                      | checks + evidence ledger    |
                                      +-----------------------------+
                                                        |
                                      PASS              | FAIL
                                        |               v
                                        |          Builder repair
                                        |               |
                                        |               +--> new candidate
                                        v
                                      +-----------------------------+
                                      | Delivery Gate               |
                                      | push -> PR -> exact HEAD    |
                                      +-----------------------------+
                                                        |
                                                        v
                                      +-----------------------------+
                                      | ChatGPT Web Reviewer        |
                                      | fresh chat / exact SHA      |
                                      +-----------------------------+
                                          |           |          |
                              REQUEST_CHANGES     APPROVED     HUMAN
                                          |           |          |
                                          v           v          v
                                      Builder fix  Release     Human
                                          |        Gate        Decision
                                          v           |
                                      Verify          v
                                          |        APPROVED
                                          v           |
                                      push new SHA    v
                                          |         STOP
                                          +--> fresh review

External review rounds > max -> REVIEW_LIMIT_REACHED -> Human
```

## 4. Physical repository layout

Target source layout:

```text
gemini-and-chatgpt/
├── SKILL.md
├── INSTALL-ANTIGRAVITY.bat
├── README.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── workflow.md
│   ├── installation.md
│   ├── roles/
│   │   ├── orchestrator-contract.md
│   │   ├── planner-contract.md
│   │   ├── architect-contract.md
│   │   ├── builder-contract.md
│   │   ├── verifier-contract.md
│   │   ├── delivery-contract.md
│   │   └── review-contract.md
│   └── policies/
│       ├── verification-policy.md
│       ├── review-policy.md
│       └── safety-release-policy.md
├── schemas/
│   ├── project-context.schema.json
│   ├── task-state.schema.json
│   ├── plan.schema.json
│   ├── verification-evidence.schema.json
│   └── checkpoint.schema.json
├── scripts/
│   ├── orchestrator.py
│   ├── state_machine.py
│   ├── task_classifier.py
│   ├── context_store.py
│   ├── plan_store.py
│   ├── verification_gate.py
│   ├── review_prompt.py
│   ├── migrate_state.py
│   ├── workflow_state.py          # compatibility wrapper during migration
│   ├── pr_context.py              # retained/hardened
│   ├── parse_review.py            # retained/hardened
│   ├── copy_review_prompt.ps1     # retained
│   └── install_agents_rule.ps1    # retained
└── docs/
    ├── architecture-current.md
    ├── architecture-awf.md
    ├── integration-matrix.md
    └── architecture-v2.md
```

Design rules:

- `SKILL.md` remains the top-level control-plane instruction but should become thinner over time.
- Detailed role authority moves into `references/roles/`.
- Machine-enforced behavior belongs in `scripts/` and `schemas/`, not duplicated in long prose prompts.
- Existing script names are preserved where compatibility is valuable.
- No AWF `workflows/` or `.brain/` tree is copied into the target project.

## 5. Runtime project-local state layout

The installed workflow uses one project-local namespace:

```text
<project>/.ai/
├── project-context.json
├── active-task.json                 # small pointer only
├── tasks/
│   └── <task-id>/
│       ├── state.json               # authoritative dynamic task state
│       ├── plan.json                # authoritative task graph when required
│       ├── plan.md                  # human-readable projection
│       ├── verification.jsonl       # append-only evidence ledger
│       ├── review-history.jsonl     # append-only parsed review history
│       └── checkpoints/
│           └── <timestamp>-<state>.json
└── review-state.json                # temporary compatibility projection only
```

`review-state.json` MUST NOT remain an independent authority. During migration it is generated from or imported into the active task state. New code reads authoritative `tasks/<task-id>/state.json` first.

## 6. Project Context Store

`project-context.json` has a lifecycle longer than one task. It stores normalized facts that are useful across tasks.

Proposed top-level model:

```json
{
  "schema_version": "2.0.0",
  "project": {
    "name": "...",
    "root": "...",
    "repository": "owner/repo"
  },
  "architecture": {
    "summary": "...",
    "components": [],
    "boundaries": [],
    "constraints": []
  },
  "conventions": {
    "coding": [],
    "testing": [],
    "git": []
  },
  "commands": {
    "install": [],
    "lint": [],
    "typecheck": [],
    "test": [],
    "build": []
  },
  "decisions": [],
  "known_risks": [],
  "environment": {
    "required_variable_names": []
  },
  "updated_at": "..."
}
```

Security rule: environment/credential NAMES may be stored; secret VALUES, tokens, passwords, private keys, PATs, cookies, or session secrets may not be persisted.

Project Context is not a transcript. Only normalized, durable facts and decisions are stored.

## 7. Authoritative Task State

`state.json` is the single source of truth for a task lifecycle.

Proposed domains:

```json
{
  "schema_version": "2.0.0",
  "identity": {},
  "classification": {},
  "requirements": {},
  "plan": {},
  "roles": {},
  "lifecycle": {},
  "implementation": {},
  "verification": {},
  "delivery": {},
  "review": {},
  "decisions": [],
  "blockers": [],
  "release": {},
  "checkpoint": {}
}
```

### 7.1 Identity

```text
id
original_request
normalized_title
created_at
updated_at
```

Task ID should be stable and filesystem-safe, for example:

```text
T-20260819-001-short-slug
```

The timestamp is not the identity by itself; the generated task ID is.

### 7.2 Classification

```text
kind
complexity_tier
risk_level
score
signals[]
architect_required
planner_required
human_precheck_required
```

### 7.3 Requirements

```text
goal
in_scope[]
out_of_scope[]
constraints[]
acceptance_criteria[]
release_constraints[]
assumptions[]
```

### 7.4 Plan

```text
required
status
plan_path
work_item_count
completed_count
current_work_item
```

The full graph lives in `plan.json`.

### 7.5 Lifecycle

```text
current_state
previous_state
state_entered_at
transition_reason
resume_state             # used when BLOCKED is cleared
local_repair_attempts
```

### 7.6 Implementation

```text
branch
candidate_sha
changed_files[]
work_items_completed[]
work_items_remaining[]
```

### 7.7 Verification

```text
overall_status
candidate_sha
required_checks[]
completed_checks[]
failed_checks[]
skipped_checks[]
evidence_ledger_path
```

### 7.8 Delivery

```text
repository
base_branch
head_branch
pr_number
pr_url
pr_state
head_sha
last_push_at
```

### 7.9 Review

```text
round
max_rounds
current_target_sha
current_verdict
current_findings[]
history_path
approval_valid
```

### 7.10 Release

```text
status
merge_policy             # default: human_only
human_required
human_reason
approved_sha
```

## 8. Plan / task graph schema

For STANDARD and COMPLEX tasks, `plan.json` is authoritative.

```json
{
  "schema_version": "2.0.0",
  "task_id": "...",
  "goal": "...",
  "acceptance_criteria": [],
  "risk_level": "...",
  "work_items": [
    {
      "id": "W1",
      "owner_role": "BUILDER",
      "objective": "...",
      "scope_hints": [],
      "dependencies": [],
      "verification": [],
      "status": "PENDING"
    }
  ],
  "release_constraints": []
}
```

Allowed work-item status:

```text
PENDING
READY
IN_PROGRESS
VERIFYING
DONE
BLOCKED
SKIPPED_WITH_REASON
```

`plan.md` is generated from `plan.json` for humans. Editing the Markdown alone does not silently mutate machine state.

## 9. Task classifier / complexity router

The router should make planning proportional to risk and scope.

### 9.1 Task kinds

Initial taxonomy:

```text
BUGFIX
FEATURE
REFACTOR
DOCS
CONFIG_BUILD
TEST
DEPENDENCY
SECURITY
ARCHITECTURE
MAINTENANCE
UNKNOWN
```

### 9.2 Complexity signals

The classifier scores or flags:

- estimated number of files/components touched;
- cross-module/cross-service scope;
- database/schema/data migration;
- public API or compatibility changes;
- authentication/authorization/security impact;
- new dependency or major dependency upgrade;
- build/CI/infrastructure impact;
- concurrency/state/data-integrity concerns;
- destructive operation risk;
- ambiguity of acceptance criteria;
- unfamiliar subsystem;
- user-visible behavior breadth.

### 9.3 Routing tiers

#### SIMPLE

Typical characteristics:

- tightly scoped;
- one/few files;
- no hard architecture/security/data triggers;
- acceptance criteria can be directly inferred.

Route:

```text
RECEIVED -> CLASSIFIED -> IMPLEMENTING
```

A minimal machine task contract is still created. No full planning ceremony.

#### STANDARD

Typical characteristics:

- multi-file or moderate feature/bugfix;
- needs explicit acceptance criteria and decomposition;
- no mandatory architecture hard trigger.

Route:

```text
RECEIVED -> CLASSIFIED -> PLANNING -> PLAN_READY -> IMPLEMENTING
```

Planner required; Architect optional.

#### COMPLEX

Triggered by high score OR hard triggers such as:

- database schema/data migration;
- public API breaking change;
- auth/security model;
- cross-service architecture;
- infrastructure/deployment topology;
- significant concurrency/data integrity;
- large dependency migration;
- broad architectural refactor.

Route:

```text
RECEIVED -> CLASSIFIED -> PLANNING(Planner + Architect) -> PLAN_READY -> IMPLEMENTING
```

A hard trigger can force COMPLEX even when the estimated file count is small.

### 9.4 Ambiguity policy

The system should infer reasonable implementation detail from repository context whenever safe. It asks the user only when ambiguity blocks correctness, creates material product choices, or crosses a human/safety boundary.

## 10. Role and authority contracts

Roles are logical responsibilities. A role does NOT imply a separate model process.

### 10.1 Orchestrator

Type: primarily deterministic.

Owns:

- task initialization;
- classifier invocation;
- state transitions;
- role activation;
- gate sequencing;
- checkpoint creation;
- retry/round counters;
- terminal-state selection.

Must NOT:

- approve its own code;
- bypass failed verification;
- invent reviewer approval;
- bypass human-required states.

### 10.2 Planner

Type: AI reasoning role, conditional.

Inputs:

- user task;
- project-context projection;
- relevant repository context;
- classifier output.

Outputs:

- normalized goal/scope;
- acceptance criteria;
- constraints/assumptions;
- work-item graph;
- verification criteria;
- release constraints.

Authority:

- may propose decomposition;
- may not write production implementation unless also explicitly acting later as Builder;
- may not change GitHub/review/release authority.

### 10.3 Architect

Type: AI reasoning role, conditional.

Activated for architecture/security/data/API hard triggers or when Planner marks architectural uncertainty.

Outputs:

- architecture decision/recommendation;
- boundary/interface changes;
- migration/compatibility concerns;
- risk controls;
- additions/changes to plan constraints.

Must NOT:

- become mandatory for simple work;
- act as final reviewer;
- override human-required safety policy.

### 10.4 Builder

Type: Antigravity/Gemini implementation authority.

Owns:

- code changes;
- implementation sequencing;
- test creation when appropriate;
- local failure diagnosis;
- reviewer-finding disposition;
- fixes.

Finding dispositions remain:

```text
ACCEPT_FINDING
REJECT_FINDING_WITH_EVIDENCE
NEEDS_HUMAN_DECISION
```

Must NOT:

- declare final merge approval;
- skip Verification Gate because a change looks trivial;
- push a fix directly to re-review without verification.

### 10.5 Verifier

Type: deterministic policy/execution plus AI diagnosis when checks fail.

Owns:

- selecting checks from policy/project capabilities;
- executing checks;
- recording evidence;
- producing PASS / FAIL / BLOCKED / PARTIAL;
- identifying skipped checks.

Must NOT:

- silently downgrade a required check;
- convert missing evidence into PASS;
- approve merge.

### 10.6 Context Manager

Type: deterministic.

Owns:

- schema validation;
- atomic state writes;
- normalized project-context updates;
- lazy projections;
- checkpoints;
- migration compatibility.

Must NOT:

- use raw chat history as the authoritative state;
- store secret values;
- make product/release decisions.

### 10.7 Delivery Gate

Type: deterministic Git/GitHub boundary.

Owns:

- candidate commit identity;
- branch/push prerequisites;
- PR create/update;
- local/PR HEAD reconciliation;
- exact SHA capture;
- invalidation of stale approval after push.

It can push only after the required Verification Gate status is acceptable.

### 10.8 External ChatGPT Web Reviewer

Type: independent external reviewer.

Owns:

- code/release review for exact `TARGET_HEAD_SHA`;
- blocking/non-blocking findings;
- security/test/readiness assessment;
- one structured verdict.

Allowed verdicts:

```text
APPROVED_TO_MERGE
REQUEST_CHANGES
NEEDS_HUMAN_DECISION
```

The reviewer never edits implementation state directly. Its output is parsed and then the Orchestrator transitions state.

### 10.9 Human authority

Human owns:

- ambiguous/high-risk decisions;
- credential/protected-operation decisions;
- unresolved Builder/Reviewer disagreement;
- review-limit resolution;
- merge policy changes;
- final merge by default.

## 11. State machine v2

### 11.1 States

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
HUMAN_DECISION
BLOCKED
FAILED
REVIEW_LIMIT_REACHED
ABORTED
```

### 11.2 Primary transitions

```text
RECEIVED
  -> CLASSIFIED

CLASSIFIED
  -> IMPLEMENTING      [SIMPLE]
  -> PLANNING          [STANDARD/COMPLEX]
  -> HUMAN_DECISION    [blocking ambiguity/risk]

PLANNING
  -> PLAN_READY
  -> HUMAN_DECISION
  -> BLOCKED
  -> FAILED

PLAN_READY
  -> IMPLEMENTING

IMPLEMENTING
  -> VERIFYING
  -> BLOCKED
  -> HUMAN_DECISION
  -> FAILED

VERIFYING
  -> PR_PREPARING      [PASS]
  -> IMPLEMENTING      [local repair required before first review]
  -> FIXING            [repair during external review cycle]
  -> HUMAN_DECISION    [required evidence unavailable/unsafe]
  -> BLOCKED
  -> FAILED

PR_PREPARING
  -> REVIEWING         [PR exists + exact HEAD captured]
  -> BLOCKED
  -> HUMAN_DECISION
  -> FAILED

REVIEWING
  -> FIXING            [REQUEST_CHANGES and rounds remain]
  -> RELEASE_GATE      [APPROVED_TO_MERGE for exact HEAD]
  -> HUMAN_DECISION    [reviewer verdict]
  -> REVIEW_LIMIT_REACHED
  -> BLOCKED
  -> FAILED

FIXING
  -> VERIFYING
  -> HUMAN_DECISION
  -> BLOCKED
  -> FAILED

RELEASE_GATE
  -> APPROVED
  -> HUMAN_DECISION

BLOCKED
  -> resume_state      [prerequisite resolved]
  -> ABORTED

HUMAN_DECISION
  -> an explicitly authorized next state
  -> ABORTED

REVIEW_LIMIT_REACHED
  -> HUMAN_DECISION
  -> ABORTED
```

`ABORTED` and `APPROVED` are terminal by default. `FAILED` is terminal unless a documented recovery action creates/resumes a new lifecycle attempt.

### 11.3 Global transition guards

- No `REVIEWING` without PR number/URL and exact full current HEAD SHA.
- No `RELEASE_GATE` unless parsed verdict is `APPROVED_TO_MERGE` and its target SHA equals the current delivery HEAD SHA exactly.
- Any pushed new HEAD clears `approval_valid`, `current_verdict`, and `approved_sha` before another review.
- `FIXING` cannot reach `REVIEWING` directly; it must pass through `VERIFYING` and delivery/head reconciliation.
- Review round may never exceed `max_rounds`.
- Required verification cannot be converted from FAIL/PARTIAL to PASS by a prompt instruction.
- Human-required flags block automated transition past the relevant gate.

### 11.4 Transition history

Every transition appends a record:

```json
{
  "from": "IMPLEMENTING",
  "to": "VERIFYING",
  "timestamp": "...",
  "reason": "candidate implementation complete",
  "actor": "ORCHESTRATOR"
}
```

State history is append-only even though current state is stored separately for fast reads.

## 12. Candidate commit and verification identity

A v2 improvement is to bind important verification evidence to an immutable local candidate SHA before push.

Preferred flow:

```text
Builder finishes a candidate
        ↓
create/update dedicated local commit
        ↓
state.implementation.candidate_sha = local HEAD
        ↓
Verification Gate runs against that candidate
        ↓
PASS evidence references candidate_sha
        ↓
push candidate_sha
        ↓
PR HEAD must equal candidate_sha
```

If verification fails and code changes, the candidate SHA changes and prior PASS evidence for the old candidate cannot authorize the new candidate.

This gives local QA the same identity discipline that already exists for external review.

Implementation may initially use a compatibility mode if changing commit ordering is too disruptive, but the target architecture is immutable-candidate-bound evidence.

## 13. Verification Gate

There is one verification authority used after initial implementation and after every accepted external-review fix.

### 13.1 Inputs

- task kind/complexity/risk;
- acceptance criteria;
- changed files/components;
- project-context command inventory;
- candidate SHA;
- previous failures/findings when relevant.

### 13.2 Check classes

```text
STATIC
  syntax / compile sanity
  formatting policy when enforced
  lint
  typecheck

FOCUSED
  tests directly covering changed behavior
  targeted integration checks

REGRESSION
  broader test suite when risk/scope requires it

BUILD
  package/build validation when supported

SECURITY / POLICY
  project-specific checks when configured
```

### 13.3 Policy by tier

SIMPLE:

- relevant static checks;
- focused test/check;
- build only when changed scope requires it.

STANDARD:

- static checks;
- focused tests;
- relevant regression suite;
- build/typecheck when supported.

COMPLEX/high-risk:

- all applicable mandatory checks;
- broader regression;
- build;
- security/migration/project-specific validations;
- unresolved skipped required checks -> HUMAN_DECISION.

### 13.4 Verification status

```text
PASS       all required checks succeeded
FAIL       one or more required checks failed
BLOCKED    check could not execute because prerequisite is unavailable
PARTIAL    non-required checks omitted OR evidence incomplete; cannot silently equal PASS
```

For delivery to independent review, policy normally requires `PASS`. A `PARTIAL` result may proceed only through an explicit rule or human decision, never by assumption.

### 13.5 Evidence record

Each JSONL record contains at minimum:

```json
{
  "id": "V-...",
  "task_id": "...",
  "candidate_sha": "40-char-sha",
  "category": "FOCUSED_TEST",
  "command": "...",
  "scope": "...",
  "status": "PASS",
  "exit_code": 0,
  "summary": "...",
  "started_at": "...",
  "finished_at": "..."
}
```

Do not persist huge raw logs in task state. Preserve concise evidence and, when needed, a local path/reference to a log artifact.

## 14. External review data flow

### 14.1 Before opening ChatGPT Web

Delivery Gate must establish:

```text
repository
PR number + URL
base branch
head branch
exact full PR HEAD SHA
local HEAD == PR HEAD
verification PASS bound to the candidate/current HEAD
```

### 14.2 Reviewer prompt projection

The prompt should be concise and generated from authoritative state, containing:

1. review contract;
2. repository + PR identity;
3. exact `TARGET_HEAD_SHA`;
4. task goal and explicit scope;
5. acceptance criteria;
6. short plan/work-item summary when applicable;
7. changed-file/diff context;
8. verification evidence summary;
9. previous blocking findings and Builder dispositions for re-review rounds;
10. required machine-readable verdict format.

Do NOT dump complete project memory or conversation history into reviewer prompts.

### 14.3 Reviewer output

`parse_review.py` must require:

- full 40-character hexadecimal `TARGET_HEAD_SHA`;
- exact equality with expected current HEAD;
- one allowed verdict;
- fail-closed handling of malformed/missing identity.

Prefix-equivalent SHA acceptance is removed.

### 14.4 Review history record

Every parsed review is append-only and records:

```text
round
target_sha
verdict
blocking_findings
non_blocking_findings
test_gaps
security_result
production_readiness
review_timestamp
```

A new HEAD never deletes old review history; it only makes the old approval non-authoritative.

## 15. Finding repair loop

```text
REQUEST_CHANGES
      ↓
Builder evaluates each finding
      ↓
+---------------------------+
| ACCEPT_FINDING            | -> repair work
| REJECT_FINDING_WITH_EVID. | -> record rationale/evidence
| NEEDS_HUMAN_DECISION      | -> HUMAN_DECISION
+---------------------------+
      ↓
FIXING
      ↓
new candidate SHA
      ↓
VERIFYING
      ↓ PASS
push / PR HEAD refresh
      ↓
invalidate prior verdict
      ↓
review round += 1
      ↓
fresh ChatGPT Web conversation
```

External review rounds and local verification retries are separate counters. The local repair loop must be bounded, but it must not consume or bypass the configured external review-round cap.

## 16. Context loading / resume model

The AWF 3-tier concept is retained but normalized around v2 state.

### Level 1 — always available

Small projection:

```text
project
active task
current state
current work item
complexity/risk
blockers
next legal action
PR/review round when present
```

### Level 2 — role-specific working context

Loaded only when needed:

```text
requirements + acceptance criteria
plan/work items
recent decisions
changed files
recent verification summary
current review findings
```

### Level 3 — deep recovery/audit

Loaded explicitly or for recovery:

```text
transition history
verification ledger
review history
checkpoints
resolved errors
older decisions
```

The loader returns role-specific projections; it does not blindly inject the full state into every prompt.

## 17. Checkpoints and recovery

Checkpoint creation is deterministic at meaningful transitions, including:

```text
PLAN_READY
before/after IMPLEMENTING batches for complex tasks
VERIFYING PASS
PR_PREPARING completion
before each REVIEWING round
REQUEST_CHANGES received
RELEASE_GATE
BLOCKED/HUMAN_DECISION
```

Checkpoint contains:

- task ID/schema version;
- state snapshot;
- candidate/head SHA identity;
- current work item;
- verification/review pointers;
- blockers;
- next legal actions.

Recovery procedure:

1. validate active-task pointer;
2. validate task state schema;
3. reconcile Git local state when repository is available;
4. reconcile PR/head SHA when a PR exists;
5. invalidate stale approval if actual HEAD differs;
6. load minimal context projection;
7. resume only from a legal state.

A checkpoint may aid recovery but cannot override live GitHub identity.

## 18. Migration from current v1 state

### 18.1 Compatibility goals

Existing components should not be broken all at once.

Migration order:

1. Add v2 schemas and state-machine implementation.
2. Add `migrate_state.py` to import existing `.ai/review-state.json`.
3. Keep `workflow_state.py` as a compatibility CLI wrapper that delegates to v2 state APIs.
4. Update `pr_context.py` to write the v2 delivery domain and optionally emit legacy projection during transition.
5. Harden `parse_review.py` to exact full SHA.
6. Update prompt generation/references.
7. Remove reliance on legacy `review-state.json` after regression coverage proves compatibility.

### 18.2 Legacy field mapping

Typical mapping:

```text
old task_id            -> identity.id
old state              -> lifecycle.current_state
old review_round       -> review.round
old max_rounds         -> review.max_rounds
old review_result      -> review.current_verdict
old ci_result          -> verification legacy/imported summary
old pr_number/url      -> delivery.pr_number/pr_url
old base_sha/head_sha  -> delivery identity
```

Imported data is tagged as migrated/legacy when evidence quality is lower than native v2 records.

## 19. Installer and activation design

Current canonical Drive inspection on 2026-08-19 shows `INSTALL-ANTIGRAVITY.bat` present in the canonical folder. Earlier audit evidence had observed it missing, so implementation work must revalidate provenance/current contents before editing it.

Target installer UX remains:

```text
Copy gemini-and-chatgpt into project root
        ↓
run INSTALL-ANTIGRAVITY.bat
        ↓
install/refresh project-local skill
        ↓
install/update AGENTS.md activation block
        ↓
Git + gh + GitHub authentication/onboarding
        ↓
ready for ordinary Antigravity tasks
```

Installer rules retained:

- one unified installer;
- no AWF global installer;
- prompts visibly use `(default Y)` / `(default N)`;
- Enter chooses the displayed default;
- idempotent re-run;
- never persist PATs/secrets;
- `.bat` parentheses/escaping receive dedicated tests.

## 20. Control-plane decomposition

`SKILL.md` should eventually contain only the high-level protocol:

- when to activate;
- invariant summary;
- orchestrator entry behavior;
- required gates;
- pointers to role/policy references;
- stop/escalation behavior.

It should NOT duplicate every schema, command, reviewer format, and role detail.

Expected relationship:

```text
SKILL.md
   |
   +--> references/roles/*
   +--> references/policies/*
   +--> references/workflow.md
   |
   +--> scripts/orchestrator.py
            |
            +--> state_machine.py
            +--> task_classifier.py
            +--> context_store.py
            +--> plan_store.py
            +--> verification_gate.py
            +--> pr_context.py
            +--> review_prompt.py
            +--> parse_review.py
```

This reduces prompt drift and makes policy testable.

## 21. Failure and escalation semantics

### BLOCKED

Use when progress could resume after an external prerequisite is fixed, for example:

- GitHub authentication missing;
- required tool unavailable;
- protected resource unavailable;
- test service unavailable.

Store `resume_state` and blocker details.

### FAILED

Use for unrecoverable workflow/runtime failure where continuing the same attempt is unsafe or invalid.

### HUMAN_DECISION

Use when:

- product ambiguity changes material behavior;
- risky/destructive operation requires approval;
- reviewer/builder disagreement cannot be resolved by evidence;
- required verification cannot be obtained but the user may consciously accept risk;
- credentials/protected interaction is needed;
- malformed/ambiguous reviewer output cannot be safely interpreted.

### REVIEW_LIMIT_REACHED

Use when another external review would exceed `max_rounds`. Never silently start round 6 under the default policy.

### ABORTED

User or authorized control-plane cancellation. Preserve state/history for audit/resume-as-new-task.

## 22. Security and integrity model

P0 rules:

- no secrets in project/task context;
- exact full SHA identity for external review;
- no approval carry-over after code changes;
- fail closed on malformed review output;
- Verification Gate cannot be overridden by prose from Builder/Planner;
- reviewer cannot write implementation state directly;
- Builder cannot mark itself externally approved;
- state writes should be atomic;
- schema version is mandatory;
- migration should preserve old state until new state validates successfully;
- GitHub/live Git identity overrides stale checkpoints.

## 23. MVP 1 implementation boundary

The first implementation increment should include only:

1. v2 project-context and task-state schemas;
2. task classifier with SIMPLE/STANDARD/COMPLEX routing;
3. Planner contract + task graph for non-trivial tasks;
4. conditional Architect contract and trigger flags;
5. deterministic state-machine v2 with transition guards/history;
6. `.ai/tasks/<task-id>/` state/context/checkpoint layout;
7. lazy context projections;
8. centralized Verification Gate + evidence ledger;
9. v1 review-state migration/compatibility wrapper;
10. exact-SHA parser hardening;
11. reviewer prompt projection with acceptance criteria + QA evidence;
12. preservation of current GitHub/ChatGPT/human-release invariants.

Explicitly outside MVP 1:

- parallel agent execution;
- Designer agent;
- adaptive language/personality framework;
- deployment automation;
- auto-update;
- Cloudflare tunnel;
- project-health scanner;
- elaborate coverage analytics;
- autonomous merge.

## 24. Regression contract required before modifying delivery/review behavior

At minimum, implementation must later cover scenarios:

```text
R01 SIMPLE bugfix bypasses deep planning but still verifies/reviews
R02 STANDARD feature creates plan and completes work items
R03 COMPLEX schema/security task activates Architect
R04 illegal state transition is rejected
R05 verification FAIL prevents push/review
R06 verification evidence is bound to candidate SHA
R07 PR HEAD mismatch blocks review
R08 exact full SHA reviewer output passes
R09 SHA prefix-only reviewer output fails closed
R10 REQUEST_CHANGES routes FIXING -> VERIFYING -> new SHA -> fresh review
R11 prior approval invalidated after push
R12 round 5 request changes leads to REVIEW_LIMIT_REACHED, not round 6
R13 malformed reviewer output -> HUMAN_DECISION
R14 skipped required check -> no automatic PASS
R15 session restart restores legal current state
R16 stale checkpoint cannot override newer GitHub HEAD
R17 migrated legacy review-state preserves review identity
R18 human-required operation cannot be auto-bypassed
R19 installer re-run is idempotent
R20 installer defaults honor `(default Y/N)` on Enter
```

## 25. Architecture acceptance criteria

Step 04 architecture is considered complete when the design explicitly answers:

- Where is authoritative project context? -> `.ai/project-context.json`.
- Where is authoritative task state? -> `.ai/tasks/<task-id>/state.json`.
- What is authoritative planning data? -> `plan.json`; `plan.md` is projection.
- Who enforces lifecycle transitions? -> deterministic state machine/orchestrator.
- How are trivial tasks kept fast? -> complexity router SIMPLE path.
- When is Architect involved? -> hard risk/architecture triggers or Planner escalation.
- Who can edit code? -> Builder.
- Who controls verification? -> centralized Verification Gate.
- What identity binds local QA? -> target candidate SHA.
- What identity binds external review? -> exact current PR HEAD SHA.
- Who provides independent verdict? -> ChatGPT Web.
- What happens after code changes? -> prior review approval invalidated.
- What happens at round limit? -> REVIEW_LIMIT_REACHED -> human.
- Who merges by default? -> human; system stops at APPROVED.
- Are AWF and `gemini-and-chatgpt` separately installed? -> no.
- Is `.brain/` retained as a second state system? -> no.

## 26. Gate status and next step

**Step 04 — Unified Architecture Design: COMPLETE when this document is approved as the design baseline.**

No implementation should begin by copying AWF files. The next implementation-preparation step should convert this architecture into a versioned implementation backlog with ordered, independently testable increments and explicit regression gates.

Recommended next command:

`Làm tiếp Bước 05 - lập implementation backlog và thứ tự triển khai MVP 1`
