# AWF Architecture Audit — Step 02

Date: 2026-08-19
Scope: `My Drive\Vibe-Code\awf-plus` (fork `BinLate/awf-plus`)
Purpose: Reverse-engineer AWF before any selective integration into `gemini-and-chatgpt`.
Status: Analysis only. No AWF behavior has been merged into `gemini-and-chatgpt` in this step.

## 1. Executive summary

AWF is primarily a **declarative orchestration framework** for Antigravity rather than a deterministic multi-agent runtime.

Its implementation is composed mainly of:

1. Markdown workflows that instruct one Antigravity agent to act in different roles/stages.
2. Markdown Skills that auto-activate cross-cutting behavior such as session restore, auto-save, adaptive language, error translation, context help, and onboarding.
3. JSON schemas/templates for project knowledge, session state, and preferences.
4. Installer scripts that register workflows/skills under Antigravity directories.
5. Repository-local `.brain/` files used as persistent project/session memory.

The strongest architectural ideas for `gemini-and-chatgpt` are:

- plan decomposition into explicit phase files;
- separation of static project memory from dynamic task/session memory;
- lazy context restore;
- checkpointing and resumability;
- explicit QA/testing stages;
- role-specific behavioral contracts.

The parts that should **not** be copied blindly are:

- slash-command-first UX;
- persona names/styles as a substitute for agent contracts;
- global AWF installer/layout;
- heuristic/prompt-only auto-save as if it were a guaranteed background runtime;
- duplicate QA logic in `/code` and `/test`;
- AWF `/review` as a replacement for independent ChatGPT Web review;
- current schema/template/path inconsistencies.

## 2. Repository topology

Observed AWF source structure:

```text
awf-plus/
├── workflows/          # Markdown lifecycle/workflow definitions
├── awf_skills/         # Auto-activated helper skills
├── schemas/            # brain/session/preferences JSON schemas
├── templates/          # example JSON files
├── docs/
├── install.ps1
├── install.sh
├── README.md
├── README.en.md
└── VERSION
```

The Windows installer defines a workflow inventory covering:

```text
Core:
init → brainstorm → plan → design → visualize → code → run

Quality:
debug → test → audit

Deploy/Maintain:
deploy → refactor → rollback

Support:
next → recap → help → customize → save_brain → review

System:
awf-update → cloudflare-tunnel
```

It installs three schemas:

- `brain.schema.json`
- `session.schema.json`
- `preferences.schema.json`

and six helper skills:

- `awf-session-restore`
- `awf-auto-save`
- `awf-adaptive-language`
- `awf-error-translator`
- `awf-context-help`
- `awf-onboarding`

## 3. Runtime model: prompt framework, not true multi-agent runtime

### 3.1 How workflows execute

AWF workflows are Markdown instruction files. The installer either:

- installs them into `global_workflows` for the legacy Antigravity layout; or
- for Antigravity 2.0+, copies each workflow Markdown file into a separate Skill directory as `SKILL.md` named `awf-<workflow>`.

Therefore the core execution engine remains Antigravity/Gemini. AWF does not introduce a separate scheduler, message bus, process supervisor, agent mailbox, distributed task queue, or independent model workers.

### 3.2 What “multi-persona” actually means

Personas are embedded prompt contracts inside workflows:

- `/plan`: “Hà” — Product Manager persona.
- `/code`: “Tuấn” — Senior Developer persona.
- `/test`: QA Engineer / Quality Guardian behavior.
- UI/design workflows use design-oriented roles.

These personas alter reasoning emphasis and communication style, but they do **not** currently have independent:

- process identity;
- persistent private state;
- ownership locks;
- input/output mailboxes;
- formal handoff messages;
- independent authority boundaries;
- concurrent execution.

For the target system, these should be treated as **role definitions**, not copied as literal multi-agent infrastructure.

## 4. Planning architecture

### 4.1 Lifecycle

The normal planning chain is roughly:

```text
/init
  ↓
/brainstorm (optional)
  ↓
/plan
  ↓
/design
  ↓
/visualize (when UI is relevant)
  ↓
/code
```

`/plan` reads a `docs/BRIEF.md` when present; otherwise it uses a structured interview and “Smart Proposal” flow.

### 4.2 Task decomposition

The most valuable planning mechanism is the generated plan directory:

```text
plans/[YYMMDD]-[HHMM]-[feature-name]/
├── plan.md
├── phase-01-setup.md
├── phase-02-database.md
├── phase-03-backend.md
├── phase-04-frontend.md
├── phase-05-integration.md
├── phase-06-testing.md
└── reports/
```

Each phase is expected to contain:

- status;
- dependencies;
- objective;
- functional requirements/tasks;
- test criteria;
- notes;
- link to the next phase.

AWF also adapts phase count by estimated complexity and splits a phase if it grows beyond 20 tasks.

### 4.3 Strengths

- Produces durable planning artifacts rather than leaving the plan only in chat.
- Gives execution a concrete task/phase boundary.
- Allows `/code phase-XX` to resume a specific unit of work.
- Creates a natural place for progress tracking and handover.
- Separates product planning from detailed DB/API design.

### 4.4 Weaknesses / integration risks

- Planning is strongly optimized for greenfield web applications; the default phase vocabulary (setup/database/backend/frontend/integration/testing) is too prescriptive for arbitrary bugfix/refactor/library/CLI tasks.
- The “3 golden questions” and repeated option menus can add friction for tasks that are already clear.
- Slash commands are the primary UX, while `gemini-and-chatgpt` requires normal natural-language task intake.
- `/plan` references `templates/visions/saas_app.md`, `landing_page.md`, `dashboard.md`, `tool.md`, and `api.md`, but the inspected `templates/` folder in this fork currently contains only `brain.example.json`, `session.example.json`, and `preferences.example.json`. No matching vision templates were found under that folder.

Conclusion: adopt the **artifact/decomposition model**, not the fixed command/dialog flow.

## 5. Execution architecture (`/code`)

`/code` acts as the primary implementation workflow.

### 5.1 Context-driven modes

It supports multiple entry modes:

- `/code phase-01` → execute one planned phase;
- `/code all-phases` → sequentially execute all phases;
- `/code <task>` → spec-based coding;
- `/code` → resume current phase/task from session state or use agile coding mode.

The current plan path, phase, task, and status are written into `.brain/session.json`.

### 5.2 Phase execution

For a phase it:

1. reads the phase file;
2. identifies tasks;
3. implements them sequentially;
4. marks completed checklist items;
5. updates plan progress;
6. runs an automatic test loop;
7. auto-saves progress.

### 5.3 Auto-test/fix loop

`/code` embeds its own verification loop:

```text
implement task
   ↓
run relevant tests
   ↓
PASS → continue
FAIL → analyze/fix/retest
            ↓
        max 3 attempts
            ↓
        stop/escalate
```

This concept is useful, but it overlaps with the separate `/test` workflow.

### 5.4 Important conflict with target workflow

AWF `/code` explicitly says not to deploy/push without asking and lists push/deploy as operations requiring permission.

The current `gemini-and-chatgpt` contract deliberately performs branch/commit/push/PR creation as the automatic post-implementation quality pipeline once installed.

Therefore AWF `/code` cannot be copied verbatim. Its repository-operation authority model conflicts with the target system.

## 6. QA/testing architecture

AWF has QA in at least two places:

### 6.1 Embedded QA in `/code`

The implementation workflow automatically runs relevant tests and performs up to three repair attempts.

### 6.2 Standalone `/test`

`/test` is a “Quality Guardian” workflow that offers:

- Quick Check;
- Full Suite;
- Manual Verify;
- automatic test-file discovery;
- quick-test creation when no test exists;
- result analysis;
- optional coverage reporting.

### 6.3 QA architecture assessment

Strengths:

- testing is first-class rather than optional;
- focused tests and full-suite tests are distinguished;
- failures are analyzed, not merely reported;
- skipped tests are represented in session state and intended to block deploy;
- QA has a separate conceptual role from coding.

Weaknesses:

- QA policy is duplicated between `/code` and `/test`;
- `/test` asks the user which strategy to run, which is undesirable for a fully automated engineering pipeline;
- there is no single deterministic policy engine deciding mandatory checks based on task risk/project capabilities;
- no exact integration exists with GitHub PR/HEAD-SHA review semantics.

For the target system, QA should become **one centralized verification gate** called by both initial implementation and every review-fix round.

## 7. AWF `/review` is not an independent release reviewer

AWF `/review` is a **Project Scanner / health and handover report**. It scans structure, package metadata, docs, `.brain`, build/lint/type health, and can produce upgrade/refactor recommendations.

It is not equivalent to the existing ChatGPT Web review contract because it does not provide:

- reviewer independence from the implementation model;
- immutable PR HEAD-SHA binding;
- structured merge verdict tied to a GitHub PR;
- stale-approval invalidation after a push;
- cross-model separation of duties.

Therefore AWF `/review` may be useful later as a project-audit capability, but **must not replace ChatGPT Web as the final release reviewer**.

## 8. Persistent context architecture (“Eternal Context”)

This is AWF’s strongest reusable subsystem conceptually.

### 8.1 Static vs dynamic split

AWF separates knowledge into:

```text
.brain/
├── brain.json        # relatively static project knowledge
├── session.json      # dynamic current-session/task state
└── preferences.json  # project-local user preferences
```

Conceptually:

**brain.json** contains:

- project identity/status;
- tech stack;
- architecture;
- database schema;
- API endpoints;
- business rules;
- features;
- project patterns/gotchas/conventions;
- environment variable names and scripts.

**session.json** contains:

- a small summary;
- current work;
- pending tasks;
- recent changes;
- encountered errors/solutions;
- decisions made;
- skipped tests;
- context checkpoints;
- auto-save configuration.

This separation is highly applicable to the target system.

### 8.2 Three-tier lazy restore

`awf-session-restore` defines:

- Level 1 (~200 tokens): summary/current task/blockers — auto-load;
- Level 2 (~800 total): decisions/pending tasks/recent files — on demand;
- Level 3 (~2000 total): errors/checkpoints/change history — deep recap.

It also defines topic-based recap/search.

This is a strong design pattern: **load only the minimum context required for the current operation**.

### 8.3 Auto-save/checkpoint model

`awf-auto-save` proposes triggers for:

- workflow end;
- user leaving patterns;
- user decisions;
- every 15 messages;
- estimated context saturation.

It stores summary/checkpoints in `session.json` and proposes 7-day snapshots for recovery.

### 8.4 Critical implementation caveat

The auto-save logic is expressed as instructions/pseudocode inside a Skill. There is no inspected AWF runtime daemon/event hook implementation that guarantees a save occurs exactly every N messages or in the background.

For `gemini-and-chatgpt`, this concept should be implemented as **deterministic state writes at known workflow transitions**, not relied on as conversational pattern matching alone.

## 9. Schema layer

### 9.1 `brain.schema.json`

Version observed: 1.1.0.

Required top-level fields:

- `meta`
- `project`
- `updated_at`

Major sections:

- `tech_stack`
- `architecture`
- `database_schema`
- `api_endpoints`
- `business_rules`
- `features`
- `knowledge_items`
- `environment`

The environment schema explicitly says environment variable **values are not stored**, only names/metadata. This is a good security property to preserve.

### 9.2 `session.schema.json`

Version observed: 2.0.0.

Required:

- `updated_at`
- `summary`

Major sections:

- `summary`
- `working_on`
- `pending_tasks`
- `recent_changes`
- `errors_encountered`
- `decisions_made`
- `skipped_tests`
- `context_checkpoints`
- `auto_save_config`

### 9.3 Schema drift discovered

`/init` currently creates a `brain.json` template with roughly:

```json
{
  "project": {...},
  "tech_stack": [],
  "features": [],
  "decisions": []
}
```

This does **not** conform to the inspected `brain.schema.json`:

- missing required `meta`;
- missing required `updated_at`;
- `tech_stack` is created as an array although schema defines it as an object;
- `decisions` is not part of the observed current top-level schema.

This demonstrates that AWF’s schemas are useful as design input but cannot be assumed internally consistent without validation/migration tooling.

## 10. Preferences / presentation layer

`preferences.schema.json`, `/customize`, and `awf-adaptive-language` form a presentation/personalization layer.

It controls concepts such as:

- communication tone;
- personality style;
- technical detail level;
- autonomy;
- output quality;
- working pace;
- feedback style;
- custom rules.

`awf-adaptive-language` reads local preferences first and then falls back to global preferences, altering terminology for newbie/basic/technical users.

This is orthogonal to the target engineering orchestration. It can remain optional/later rather than being part of the first integration MVP.

### Path drift

The installer’s Antigravity resources live under paths such as:

```text
~/.gemini/antigravity/
```

while `/customize` and `awf-adaptive-language` use global preference paths under:

```text
~/.antigravity/preferences.json
```

This may be intentional separation, but it creates path-model inconsistency and should not be inherited without an explicit directory convention.

## 11. Installer architecture

`install.ps1` supports three modes:

- `1.0` — legacy global workflows;
- `2.0` — workflows registered as Skills;
- `both` — install both layouts.

For Antigravity 2.0+ it converts each workflow into a Skill by copying the workflow Markdown to:

```text
<skills-dir>/awf-<workflow>/SKILL.md
```

It then also installs the dedicated helper Skills.

This achieves compatibility, but for `gemini-and-chatgpt` it would create unnecessary framework stacking and a large global skill surface. The target project should retain a single project-local installer and a single unified activation layer.

## 12. Data/control-flow model

AWF’s effective architecture can be modeled as:

```text
User slash command / trigger
        ↓
Workflow Markdown / Skill
        ↓
Role/persona instructions
        ↓
Read .brain + project docs
        ↓
Perform planning / code / QA operation
        ↓
Write plan/docs/code
        ↓
Update .brain/session.json
        ↓
Auto-save / recap helper behavior
        ↓
Suggest next slash command
```

There is no central executable state machine that enforces all legal transitions. The workflow chain is predominantly enforced through instructions and conventions.

## 13. Architectural strengths worth preserving

### High-value concepts

1. **Durable planning artifacts** rather than chat-only plans.
2. **Phase/task decomposition** with dependencies and test criteria.
3. **Static vs dynamic context split** (`brain` vs `session`).
4. **Lazy context loading** to control token usage.
5. **Checkpoint/recovery mindset**.
6. **Role-specialized reasoning** (PM / developer / QA / designer).
7. **QA as a first-class stage**.
8. **Known errors/decisions/conventions as structured memory**.
9. **Do not store secret values** in project context.
10. **Progress can resume from a named phase/task**.

## 14. Architectural weaknesses / risks

### A. No true multi-agent execution

Personas are role prompts executed by the same underlying agent. There are no formal agent boundaries/handoffs.

### B. No deterministic orchestration engine

State transitions, auto-save triggers, and workflow routing are mainly prompt-defined rather than code-enforced.

### C. Duplicate QA policy

`/code` and `/test` both own testing behavior, creating potential policy drift.

### D. Command-first UX

AWF expects users to navigate workflows with `/plan`, `/code`, `/test`, etc.; target UX requires automatic routing from normal task requests.

### E. Schema drift

At least `/init` and `brain.schema.json` are inconsistent.

### F. Missing referenced planning assets

`/plan` refers to `templates/visions/*`, but those assets are not present in the inspected `templates/` folder of this fork.

### G. Repository authority conflict

AWF `/code` requires asking before push/deploy; `gemini-and-chatgpt` needs automated branch/push/PR progression after implementation.

### H. Internal review is not independent review

AWF `/review` is a project scan, not an immutable-SHA external release gate.

### I. Heuristic context saturation

Token estimation based on message/code-block counts is approximate and should not be treated as a correctness-critical trigger.

### J. Global installation footprint

Installing every workflow as a global skill risks trigger ambiguity, duplication, and harder upgrades when combined with a project-local framework.

## 15. Preliminary integration signals (not the final matrix)

The formal Adopt / Adapt / Reject / Later matrix belongs to Step 03. Based on Step 02 evidence, the current preliminary signals are:

| AWF concept | Preliminary signal | Reason |
|---|---|---|
| Plan artifacts + phase decomposition | ADAPT / high value | Strong durable work breakdown, but too web-app-specific |
| Static project memory (`brain`) | ADAPT / high value | Good separation from transient task state |
| Dynamic session/task memory | ADAPT / high value | Good basis for resumability |
| 3-tier lazy restore | ADAPT / high value | Useful token/context discipline |
| Checkpoints/snapshots | ADAPT | Needs deterministic implementation |
| PM/Dev/QA/Designer personas | ADAPT | Convert to role contracts, not named personalities |
| Auto-test/fix loop | ADAPT | Merge into one QA gate with risk-aware policy |
| `/test` command UX | REJECT as primary UX | Automatic QA should choose checks itself |
| `/review` as final reviewer | REJECT | Keep independent ChatGPT Web reviewer |
| Slash-command lifecycle | REJECT as primary UX | Normal user tasks must auto-route |
| Global AWF installer | REJECT | Preserve one project-local installer |
| Adaptive language/preferences | LATER | Useful UX layer, not core orchestration |
| Error translator | LATER | Nice-to-have, not engineering-control primitive |
| AWF deploy/rollback | LATER | Release gate/PR workflow is higher priority |

## 16. Recommended conceptual extraction for Step 03

For the next comparison step, map AWF concepts into five candidate target subsystems:

```text
1. TASK INTAKE + PLANNER
   ← /plan decomposition concepts

2. ROLE CONTRACTS
   ← PM / Architect / Coder / QA persona responsibilities

3. CONTEXT STORE
   ← brain.json + session.json + lazy restore

4. VERIFICATION GATE
   ← /code auto-test + /test QA concepts

5. DELIVERY / REVIEW / RELEASE
   ← KEEP gemini-and-chatgpt implementation
      GitHub PR + exact HEAD SHA + ChatGPT Web + fix/re-review + human gate
```

The target should not install AWF beside `gemini-and-chatgpt`. It should selectively re-express the useful AWF concepts inside one unified system.

## 17. Step 02 conclusion

AWF provides valuable **workflow design patterns**, especially planning decomposition and persistent context, but its current implementation is not yet the multi-agent engineering runtime that the target project needs.

The correct strategy is therefore:

```text
Study AWF semantics
      ↓
Extract useful contracts/data models
      ↓
Normalize inconsistent schemas/paths
      ↓
Replace command routing with task classification
      ↓
Turn personas into explicit role contracts
      ↓
Centralize QA
      ↓
Connect all of it to the existing deterministic PR/SHA/reviewer/release gate
```

No code should be merged from AWF until the Step 03 comparison matrix identifies exactly which subsystem is adopted, adapted, rejected, or deferred.
