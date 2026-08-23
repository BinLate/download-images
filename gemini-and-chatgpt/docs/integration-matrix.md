# AWF ↔ gemini-and-chatgpt Integration Matrix — Step 03

Date: 2026-08-19  
Canonical target source: `My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt`  
Source basis:
- `docs/architecture-current.md` — current `gemini-and-chatgpt` architecture audit
- `docs/architecture-awf.md` — AWF architecture audit

Status: **Architecture decision only. No AWF runtime/code integration in this step.**

---

## 1. Decision summary

The unified product should evolve **from `gemini-and-chatgpt`**, not from AWF.

AWF contributes selected front-half capabilities:

- planning artifacts;
- task decomposition;
- persistent project/task context;
- lazy context restore;
- checkpoints/resume;
- role-specific reasoning contracts;
- QA concepts.

`gemini-and-chatgpt` remains authoritative for the delivery/review/release half:

- automatic workspace activation;
- Antigravity/Gemini as builder/orchestrator;
- Git/GitHub branch/commit/push/PR lifecycle;
- exact PR HEAD SHA identity;
- external ChatGPT Web review;
- structured review verdict parsing;
- stale-approval invalidation;
- review/fix loop capped at 5 rounds;
- human safety/release gate;
- no auto-merge by default.

Target principle:

```text
AWF ideas → normalize/rewrite into gemini-and-chatgpt
NOT
Install AWF + install gemini-and-chatgpt + bridge them
```

---

## 2. Classification rules

Each candidate subsystem receives one decision:

- **ADOPT** — retain substantially as-is because it already fits the target architecture.
- **ADAPT** — retain the concept/contract, but rewrite or merge it into the unified architecture.
- **REJECT** — do not bring it into the unified core because it conflicts with target invariants or creates duplicate infrastructure.
- **LATER** — potentially useful, but not justified for the first unified architecture/MVP.

Priority:

- **P0** — prerequisite or architecture invariant.
- **P1** — first integration MVP.
- **P2** — second-stage hardening/expansion.
- **P3** — optional/later.

---

## 3. Non-negotiable target invariants

The following are preserved regardless of AWF integration:

1. User gives ordinary natural-language coding tasks; explicit `/plan`, `/code`, or skill naming is not required.
2. `AGENTS.md`/workspace rules may auto-activate the unified workflow.
3. Antigravity/Gemini remains the implementation authority.
4. ChatGPT Web remains an independent reviewer, not an internal Gemini persona.
5. A GitHub PR must exist before final independent review.
6. Every independent review is bound to the exact current PR HEAD SHA.
7. A new pushed HEAD invalidates every prior approval.
8. Reviewer output is machine-parsed and fails closed when malformed or stale.
9. Gemini evaluates findings as evidence-bearing hypotheses; it does not blindly obey them.
10. Fixes must pass relevant local QA before push/re-review.
11. Review loop remains capped at 5 rounds by default.
12. `APPROVED_TO_MERGE` stops before merge unless the user explicitly changes policy.
13. High-risk or unresolved ambiguity escalates to a human gate.
14. One unified installer/activation model; no stacked AWF installer.
15. Persistent context must never store secret values.

---

## 4. Integration Matrix — core orchestration

| Source capability | Current state | AWF contribution | Decision | Priority | Target subsystem | Rationale |
|---|---|---|---|---|---|---|
| Natural-language task intake | Strong in `gemini-and-chatgpt` via auto-activation intent | AWF is slash-command-first | **ADOPT current / REJECT AWF UX** | P0 | `AGENTS.md` + unified task router | Slash commands would regress zero-friction UX. They may remain aliases later, never primary UX. |
| Auto-activation | `install_agents_rule.ps1` injects canonical `AGENTS.md` block | AWF uses installed workflows/skills | **ADOPT current** | P0 | Activation layer | Existing mechanism directly serves the desired user experience. |
| Workflow orchestration | Mostly prompt-driven; state persisted but transitions not enforced | AWF also mostly prompt-driven and convention-based | **ADAPT both** | P1 | Deterministic orchestrator/state machine | Neither system currently provides a strong executable lifecycle. Unified design should add one rather than stack two prompt frameworks. |
| Task complexity routing | Not explicit | AWF has simple/medium/complex phase reasoning | **ADAPT** | P1 | Task classifier/router | Use complexity to decide whether deep planning/architecture roles are needed. Avoid running a full team pipeline for trivial edits. |
| State machine | `workflow_state.py` stores named states but permits arbitrary valid transitions | AWF session status is descriptive, not a legal transition graph | **ADAPT current** | P1 | `state_machine` | Extend current state model with validated transitions, blockers, recovery, review-limit terminal state, and context checkpoints. |
| Resume/recovery | Review state can be reopened manually | AWF has session restore/checkpoints/handover concepts | **ADAPT** | P1 | Context + recovery layer | Deterministic resume is one of AWF's strongest ideas, but it must be tied to real state transitions rather than chat heuristics. |
| User-facing slash commands | Not needed | Core AWF interaction model | **REJECT as primary UX** | P0 | Optional compatibility aliases only | Conflicts with ordinary-task UX. |

---

## 5. Integration Matrix — planning and decomposition

| AWF capability/file | Value | Decision | Priority | Target form | Required changes |
|---|---|---|---|---|---|
| `workflows/plan.md` durable plan artifacts | High | **ADAPT** | P1 | Planner role + structured plan generator | Remove mandatory 3-question flow; infer from task/context first; ask only when blocking ambiguity exists. |
| Phase/task decomposition | Very high | **ADAPT** | P1 | Task graph / phase artifacts | Make decomposition task-type neutral; do not hard-code web-app phases for bugfix/refactor/CLI/library tasks. |
| Phase dependencies | High | **ADOPT concept** | P1 | Explicit dependency edges | Preserve objective, dependencies, tasks, test criteria, completion criteria. |
| Phase progress tracking | High | **ADAPT** | P1 | Machine-readable task state + optional Markdown view | Avoid making Markdown checkboxes the sole source of truth. |
| `brainstorm.md` | Useful for vague product ideation | **LATER** | P3 | Optional ideation role | Not needed for ordinary coding tasks; route only when task intent is exploratory. |
| `design.md` | Useful for architecture-heavy work | **ADAPT** | P2 | Conditional Architect role | Trigger only for schema/API/security/architecture-impact tasks; not mandatory after every plan. |
| `visualize` workflow | Useful for UI work | **LATER** | P3 | Conditional Design/UI role | Keep outside core engineering MVP. |
| AWF vision templates referenced by `/plan` | Concept useful but source currently inconsistent/missing | **REJECT current files / LATER new templates** | P3 | New task templates if justified | Do not inherit broken references. |
| `plans/<timestamp>-<feature>/...` folder convention | Useful but prescriptive | **ADAPT** | P1 | Task-ID-based durable plan store | Prefer stable task identity over timestamp-only identity. |

### Recommended planning contract

Every non-trivial plan should normalize to:

```text
Task
├── goal
├── scope
├── constraints
├── acceptance_criteria[]
├── risk_level
├── dependencies[]
├── work_items[]
│   ├── id
│   ├── owner_role
│   ├── objective
│   ├── files/scope_hint
│   ├── dependencies[]
│   ├── verification[]
│   └── status
└── release_constraints
```

The exact implementation format will be decided in the architecture-design step; the important decision here is that the **machine-readable task graph is authoritative**, while a Markdown plan is a human-readable projection.

---

## 6. Integration Matrix — multi-agent/persona model

| AWF concept | Current reality in AWF | Decision | Priority | Unified interpretation |
|---|---|---|---|---|
| PM persona “Hà” | Prompt persona inside `/plan` | **ADAPT** | P1/P2 | `Planner` role contract, no named-character dependency |
| Senior Dev “Tuấn” | Prompt persona inside `/code` | **ADAPT into existing Builder** | P1 | Existing Builder contract remains implementation authority; selectively import useful constraints |
| QA persona | Prompt role/workflow | **ADAPT** | P1 | `QA/Verification` role with explicit evidence contract |
| Designer persona | Prompt role | **LATER** | P3 | Optional Design role for UI-heavy tasks |
| Independent reviewer persona inside AWF | AWF `/review` is project scanner, not release reviewer | **REJECT as release reviewer** | P0 | ChatGPT Web remains external reviewer |
| Persona tone/style | Communication decoration | **LATER** | P3 | Separate presentation preference from engineering authority |
| “Multi-agent” as multiple names | No real independent workers/state | **REJECT literal copying** | P0 | Build role/authority contracts first; runtime may use one or several model invocations later |

### Role model selected for the unified architecture

Core roles:

```text
ORCHESTRATOR
├── PLANNER          (conditional)
├── ARCHITECT        (conditional)
├── BUILDER          (Gemini/Antigravity)
├── QA / VERIFIER
├── CONTEXT MANAGER  (mostly deterministic storage/recovery)
└── DELIVERY GATE
        ↓
EXTERNAL CHATGPT WEB REVIEWER
        ↓
HUMAN RELEASE/SAFETY GATE
```

Important: a role does **not** automatically mean a separate model/process. Some roles should be deterministic scripts/contracts. This prevents agent explosion.

---

## 7. Integration Matrix — persistent context and memory

| AWF capability | Decision | Priority | Target subsystem | Adaptation rule |
|---|---|---|---|---|
| `brain.json` static project knowledge | **ADAPT** | P1 | Project Context Store | Rewrite schema; keep architecture, conventions, business rules, environment variable names, known constraints; never secret values. |
| `session.json` dynamic work state | **ADAPT** | P1 | Task/Session Store | Merge concept with current `.ai/review-state.json` lifecycle; avoid two independent sources of truth. |
| Static vs dynamic context split | **ADOPT concept** | P1 | Context model | Preserve distinction between durable project facts and per-task volatile state. |
| 3-tier lazy restore | **ADAPT** | P1 | Context loader | Load minimal summary by default; expand only when planner/builder/QA needs more detail. |
| Topic-based recap/search | **LATER** | P2/P3 | Context query API | Valuable after normalized context exists. |
| Workflow-end checkpoint | **ADOPT concept** | P1 | Orchestrator hooks | Save at deterministic transitions. |
| Every-15-message checkpoint | **REJECT as guarantee** | P0 | None | Message-count heuristic is not a reliable runtime event mechanism. |
| “User leaving” pattern detection | **REJECT core** | P3 | Optional UX only | Do not make correctness depend on language-pattern guessing. |
| Context saturation warning | **ADAPT** | P2 | Context manager | Use actual runtime capabilities/size signals where available; fall back conservatively. |
| 7-day snapshots | **ADAPT** | P2 | Recovery store | Useful, but retention/config must be explicit and local. |
| Handover document | **ADAPT** | P2 | Resume artifact | Generate from authoritative state, not from free-form chat memory. |
| `.brain/` directory name | **REJECT as target namespace** | P0 | Use unified `.ai/` namespace | Avoid two branded state trees and preserve compatibility with current state location. |

### Selected context namespace direction

Do not create both `.brain/` and `.ai/`.

The unified system should converge on one project-local state root:

```text
.ai/
├── project-context.*
├── task-state.*
├── review-state.*      # compatibility/migration boundary initially
├── checkpoints/
└── plans/
```

Exact filenames/formats are deferred to the design step, but the **single `.ai/` namespace** is decided here.

---

## 8. Integration Matrix — QA, verification, and repair

| Capability | Current `gemini-and-chatgpt` | AWF | Decision | Priority | Target behavior |
|---|---|---|---|---|---|
| Builder local verification | Required by Builder/workflow contract | `/code` auto-test loop | **ADAPT/merge** | P1 | One centralized Verification Gate called after implementation and every accepted reviewer fix. |
| Focused tests | Implicit/project-specific | Explicit Quick Check | **ADOPT concept** | P1 | Run task-relevant checks first. |
| Full regression suite | Recommended/relevant checks | Full Suite option | **ADAPT** | P1 | Decide automatically based on project capability/risk, not ask every time. |
| Test discovery | Not normalized | `/test` scans test patterns | **ADAPT** | P2 | Verification detector discovers project commands/configuration. |
| Quick test generation | Not standardized | AWF proposes ad-hoc quick scripts | **LATER / guarded** | P3 | Only when meaningful and safe; never substitute weak ad-hoc checks for real tests silently. |
| Coverage | Not core | Optional | **LATER** | P3 | Risk/project dependent. |
| Skipped-test tracking | Not structured | Explicit in session schema | **ADAPT** | P1/P2 | Persist skipped/disabled checks as release evidence; blockers depend on relevance/risk. |
| Auto-fix test failure | Builder diagnoses failures | AWF max-3 repair loop | **ADAPT** | P1 | Bounded repair attempts with evidence; do not create a second loop that competes with 5-round external review loop. |
| Reviewer-finding repair | Strong existing protocol | Not tied to external reviewer | **ADOPT current** | P0 | Preserve ACCEPT / REJECT_WITH_EVIDENCE / HUMAN_DECISION semantics. |
| QA evidence ledger | Limited | Partial session concepts | **ADAPT** | P1/P2 | Persist command, status, scope, timestamp, relevant output summary, and HEAD association. |

### Selected QA rule

There will be **one verification policy engine**, not separate `/code` QA and `/test` QA authorities.

```text
IMPLEMENT/FIX
   ↓
VERIFICATION GATE
   ├── static checks
   ├── focused tests
   ├── regression tests (when required)
   ├── build/type/lint as supported
   └── evidence ledger
   ↓ PASS
PUSH/PR or RE-REVIEW
```

---

## 9. Integration Matrix — GitHub, independent review, and release

| Component | Decision | Priority | Notes |
|---|---|---|---|
| GitHub PR as shared state bus | **ADOPT** | P0 | Remains delivery/review source of truth. |
| `pr_context.py` local HEAD == PR HEAD enforcement | **ADOPT + harden** | P0/P1 | Keep fail-closed behavior; integrate richer CI/evidence context later. |
| Exact SHA reviewer target | **ADOPT** | P0 | Core invariant. |
| `parse_review.py` structured verdict parsing | **ADAPT** | P0/P1 | Preserve fail-closed parsing; remove abbreviated/prefix SHA acceptance so exact SHA truly means exact. |
| `review-contract.md` | **ADOPT** | P0 | May later receive task plan + QA evidence fields, but independence and verdict contract remain. |
| Fresh ChatGPT Web conversation per round | **ADOPT** | P0 | Prevent reviewer context contamination/stale approval. |
| Clipboard prompt helper | **ADOPT** | P0 | Existing deterministic bulk paste behavior remains useful. |
| AWF `/review` as final reviewer | **REJECT** | P0 | It is a project scanner, not independent release authority. |
| AWF project scanner capability | **LATER** | P3 | Could become optional project-health/audit role. |
| Auto-merge | **REJECT default** | P0 | Stay OFF. |
| AWF deploy workflow | **REJECT from core pipeline** | P0 | Unified core stops at approved-to-merge; deployment is a separate future capability. |

---

## 10. Integration Matrix — installer and distribution

| Source behavior | Decision | Priority | Target |
|---|---|---|---|
| Current single `INSTALL-ANTIGRAVITY.bat` UX | **ADOPT as target UX** | P0 | One installer in canonical `gemini-and-chatgpt` source. |
| Current canonical-folder installer absence | **MUST RECONCILE BEFORE IMPLEMENTATION** | P0 | Restore/reconcile canonical source deliberately; do not copy blindly from stale parallel folder. |
| `(default Y)` / `(default N)` prompt convention | **ADOPT** | P0 | Enter selects displayed default. |
| AWF `install.ps1` / `install.sh` global workflow installer | **REJECT** | P0 | Would stack frameworks and duplicate skill surfaces. |
| AWF 1.0/2.0/both compatibility modes | **REJECT core** | P2/P3 | Only revisit if unified product later needs cross-version compatibility. |
| AWF global skills registration | **REJECT** | P0 | Keep unified project-local skill/activation model. |
| AWF onboarding helper skill | **REJECT as separate skill / ADAPT useful onboarding ideas** | P2 | Existing installer already owns Git/GitHub onboarding. |
| AWF updater | **LATER** | P3 | Unified product may eventually need update/migration tooling, but not AWF's separate updater. |

---

## 11. Integration Matrix — presentation/preferences/support features

| AWF feature | Decision | Priority | Rationale |
|---|---|---|---|
| `preferences.json` communication preferences | **LATER** | P3 | Orthogonal to core software-team reliability. |
| Adaptive technical language | **LATER** | P3 | Useful UX, not required for orchestration MVP. |
| Mentor/Strict Coach personalities | **REJECT from core authority model / LATER UX** | P3 | Tone must not change engineering gates or safety invariants. |
| Error translator | **LATER** | P3 | Useful for novice-facing UX only. |
| Context help | **LATER** | P3 | Build after context layer is deterministic. |
| AWF onboarding | **LATER/merge into installer UX** | P2 | No separate helper skill. |
| Cloudflare tunnel workflow | **REJECT** | P3 | Unrelated to target core product. |

---

## 12. Source-file-level disposition

### AWF workflows

| AWF source | Disposition |
|---|---|
| `workflows/init.md` | **REJECT workflow; ADAPT context-bootstrap idea** |
| `workflows/brainstorm.md` | **LATER** |
| `workflows/plan.md` | **ADAPT — high value** |
| `workflows/design.md` | **ADAPT — conditional** |
| `workflows/visualize.md` | **LATER** |
| `workflows/code.md` | **ADAPT selected execution/phase/test ideas into existing Builder; do not copy authority model** |
| `workflows/run.md` | **LATER / fold into verification when useful** |
| `workflows/debug.md` | **ADAPT repair-analysis ideas** |
| `workflows/test.md` | **ADAPT into centralized Verification Gate** |
| `workflows/audit.md` | **LATER** |
| `workflows/deploy.md` | **REJECT from core** |
| `workflows/refactor.md` | **REJECT as required special workflow; normal task classifier can label refactor tasks** |
| `workflows/rollback.md` | **LATER recovery capability** |
| `workflows/next.md` | **ADAPT into automatic next-state determination** |
| `workflows/recap.md` | **ADAPT into context restore, not a required command** |
| `workflows/help.md` | **LATER** |
| `workflows/customize.md` | **LATER** |
| `workflows/save_brain.md` | **ADAPT into deterministic context writes/checkpoints** |
| `workflows/review.md` | **REJECT as final reviewer; LATER as project scanner** |
| `workflows/awf-update.md` | **REJECT / future unified updater only** |
| `cloudflare-tunnel` workflow | **REJECT** |

### AWF helper skills

| AWF skill | Disposition |
|---|---|
| `awf-session-restore` | **ADAPT — high value** |
| `awf-auto-save` | **ADAPT semantics; rewrite deterministic triggers** |
| `awf-adaptive-language` | **LATER** |
| `awf-error-translator` | **LATER** |
| `awf-context-help` | **LATER** |
| `awf-onboarding` | **REJECT separate skill; merge useful ideas into unified installer** |

### AWF schemas/templates

| Source | Disposition |
|---|---|
| `schemas/brain.schema.json` | **ADAPT — design input only; rewrite and validate** |
| `schemas/session.schema.json` | **ADAPT — design input only; merge with current workflow/review state** |
| `schemas/preferences.schema.json` | **LATER** |
| `templates/brain.example.json` | **REFERENCE ONLY** |
| `templates/session.example.json` | **REFERENCE ONLY** |
| `templates/preferences.example.json` | **LATER** |
| Missing `templates/visions/*` references | **DO NOT INHERIT** |

### Current `gemini-and-chatgpt` components

| Current source | Disposition |
|---|---|
| `SKILL.md` | **ADAPT as unified control plane; reduce monolithic responsibilities over time** |
| `AGENTS.md` installer rule | **ADOPT** |
| `references/builder-contract.md` | **ADOPT/extend into formal Builder role contract** |
| `references/review-contract.md` | **ADOPT** |
| `references/workflow.md` | **ADAPT to state-machine v2/context/QA architecture** |
| `references/installation.md` | **ADAPT after architecture implementation** |
| `scripts/workflow_state.py` | **ADAPT into validated state machine** |
| `scripts/pr_context.py` | **ADOPT + integrate richer evidence** |
| `scripts/parse_review.py` | **ADAPT; enforce exact SHA** |
| `scripts/copy_review_prompt.ps1` | **ADOPT** |
| `scripts/install_agents_rule.ps1` | **ADOPT** |
| `agents/openai.yaml` | **ADAPT metadata later** |
| Canonical `INSTALL-ANTIGRAVITY.bat` | **P0 source-integrity reconciliation required before installer work** |

---

## 13. Unified target subsystem map

The following logical architecture is selected as the target direction for the next design step:

```text
User natural-language task
        ↓
ACTIVATION / TASK INTAKE
        ↓
TASK CLASSIFIER / COMPLEXITY ROUTER
        ↓
┌──────────────────────────────────────────────┐
│ PLANNING LAYER                              │
│  Planner (conditional)                     │
│  Architect (conditional)                   │
│  Task decomposition + acceptance criteria  │
└──────────────────────────────────────────────┘
        ↓
CONTEXT / STATE LAYER
  project context + task state + checkpoints
        ↓
BUILDER — Antigravity/Gemini
        ↓
CENTRAL VERIFICATION GATE
        ↓
DELIVERY LAYER
  branch → commit → push → PR
        ↓
PR CONTEXT + EXACT HEAD SHA
        ↓
EXTERNAL CHATGPT WEB REVIEWER
        ↓
┌────────────────────┬────────────────────────┐
│ REQUEST_CHANGES    │ APPROVED_TO_MERGE      │
│        ↓            │          ↓             │
│ Builder evaluates  │ Release/human gate     │
│ Fix → Verify       │ STOP before merge      │
│ Push → new SHA     │                        │
│ Fresh review       │                        │
└────────────────────┴────────────────────────┘
        ↓
max 5 review rounds / human escalation
```

---

## 14. Proposed state-machine v2 boundary

The design step should formalize at least these states:

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

Required transition invariants include:

- `REVIEWING` requires PR identity + exact current HEAD SHA.
- `APPROVED` requires parsed `APPROVED_TO_MERGE` for the exact current HEAD SHA and acceptable verification evidence.
- Any pushed new HEAD clears approval/review result and returns through verification/review.
- `FIXING` cannot push directly to review without `VERIFYING`.
- Round > configured maximum transitions to `REVIEW_LIMIT_REACHED`, never silently starts another review.
- Human-required conditions cannot be bypassed by a persona/agent.

---

## 15. Context/state unification decision

Do not maintain:

```text
.brain/session.json
AND
.ai/review-state.json
AND
another agent state file
```

as independent authorities.

The future state model should have **one authoritative task state** with distinct sections/domains for:

```text
identity
classification
requirements
plan/decomposition
role assignments
implementation progress
verification evidence
GitHub/PR identity
review rounds/findings
decisions/blockers
checkpoints/recovery
release state
```

A separate project-context store may remain because its lifetime differs from task state.

Compatibility with existing `.ai/review-state.json` should be handled by migration/adapter logic, not parallel permanent state.

---

## 16. What the first integration MVP should contain

**MVP 1 — high value, bounded scope:**

1. Task classifier / complexity tier.
2. Planner contract for non-trivial tasks.
3. Task decomposition with acceptance + verification criteria.
4. Static project context + dynamic task state under one `.ai/` namespace.
5. Deterministic checkpoints at state transitions.
6. Lazy context restore.
7. Central Verification Gate.
8. State-machine v2 transition enforcement.
9. Feed plan/acceptance/QA evidence into the existing reviewer prompt.
10. Preserve current GitHub/HEAD/ChatGPT/review-limit/human-gate behavior.

**Explicitly not in MVP 1:**

- UI Designer agent;
- parallel/concurrent agent execution;
- global personalization framework;
- AWF slash commands as required UX;
- deployment automation;
- auto-update;
- project-health scanner;
- cloud tunnels;
- multiple autonomous model workers merely to claim “multi-agent”.

---

## 17. Preconditions before implementation

### Gate A — canonical source integrity (P0)

Before source integration begins:

- reconcile the missing `INSTALL-ANTIGRAVITY.bat` in canonical `awf-plus\gemini-and-chatgpt`;
- identify whether the parallel older folder contains newer/unique source that belongs in canonical source;
- do a file-by-file diff before moving anything;
- fix canonical README path drift;
- do not blindly overwrite canonical files.

### Gate B — architecture design

Before coding MVP 1, define:

- authoritative state schema;
- project-context schema;
- state transition graph;
- task complexity classifier inputs;
- role contracts and authority;
- plan/task artifact format;
- QA evidence format;
- migration behavior for `.ai/review-state.json`;
- reviewer prompt additions;
- exact-SHA parsing hardening.

### Gate C — regression contract

The 15 invariants in section 3 must be turned into scenario/acceptance tests before changing the delivery/review pipeline.

---

## 18. Risk register

| Risk | Severity | Mitigation |
|---|---|---|
| Two competing sources of state (`.brain` vs `.ai`) | High | Single `.ai/` namespace + schema migration. |
| AWF planning overhead on trivial tasks | High UX risk | Complexity router; SIMPLE path bypasses deep planning. |
| Persona proliferation mistaken for real architecture | Medium/High | Role contracts + authority boundaries; separate model only when justified. |
| QA duplication | High | One centralized Verification Gate. |
| External reviewer independence accidentally weakened | Critical | Keep ChatGPT Web outside Gemini team and exact-SHA bound. |
| Schema drift inherited from AWF | High | New versioned schemas + validation + migrations. |
| Prompt-only state transitions are skipped | High | Deterministic state-machine script/API. |
| Installer framework stacking | High | One unified installer only. |
| Canonical source loses newer files from old folder | High | P0 diff/reconciliation before source migration. |
| Context becomes a transcript dump | Medium | Store normalized facts/decisions/evidence, not raw conversation by default. |
| Excessive agent invocations increase latency/cost | Medium | Role ≠ process; complexity-based activation. |
| Reviewer prompt becomes bloated | Medium | Lazy context + concise plan/QA evidence projection. |

---

## 19. Final ADOPT / ADAPT / REJECT / LATER summary

### ADOPT

- current `AGENTS.md` auto-activation model;
- Builder ↔ external Reviewer separation;
- GitHub PR as shared delivery/review state;
- exact PR HEAD review invariant;
- fresh ChatGPT Web review round;
- fail-closed structured reviewer verdict;
- builder evidence-based finding disposition;
- 5-round limit;
- human release/safety gate;
- no auto-merge default;
- AWF concepts of phase dependencies and static/dynamic context separation.

### ADAPT

- AWF planning;
- task decomposition;
- conditional architecture role;
- AWF persona semantics → formal role contracts;
- Eternal Context → deterministic `.ai/` context/state layer;
- lazy restore;
- checkpoints/handover;
- AWF QA/testing ideas → one Verification Gate;
- current workflow state → enforced state machine v2;
- current reviewer prompt → add concise acceptance/QA evidence;
- current review parser → exact full SHA equality.

### REJECT

- AWF as a separately installed framework;
- slash-command-first primary UX;
- global AWF installer layout;
- `.brain/` as a second permanent state namespace;
- persona names as the architecture itself;
- heuristic every-N-message auto-save as a correctness guarantee;
- AWF `/review` as final release reviewer;
- AWF deploy flow in the core PR-review pipeline;
- mandatory special refactor workflow;
- missing/broken template references;
- Cloudflare tunnel capability in the unified core.

### LATER

- brainstorm/ideation mode;
- visual designer role;
- project-health scanner;
- preferences/adaptive language/personality;
- error translator/context help;
- coverage policy sophistication;
- snapshot retention tooling;
- parallel agent execution;
- unified updater;
- deployment workflows.

---

## 20. Gate status

**Bước 03 — Architecture Comparison + Integration Matrix: COMPLETE.**

This matrix authorizes the next step to design the **unified target architecture**. It does **not** authorize blind source copying from AWF.

Recommended next command:

`Làm tiếp Bước 04 - thiết kế kiến trúc hợp nhất gemini-and-chatgpt v2`
