---
name: gemini-and-chatgpt
description: "Automatically orchestrate normal Antigravity coding work as a proportional AI software-engineering workflow with deterministic task classification, durable planning for non-trivial tasks, SHA-bound verification evidence, GitHub Pull Request delivery, and an independent fresh ChatGPT Web review of the exact PR HEAD. Use for implementation, bug fixing, refactoring, feature, test, configuration, dependency, security, and architecture-related coding tasks after this skill is installed in a project. Do not require the user to explicitly name this skill in each coding prompt."
---

# Gemini + ChatGPT v2 Software Team

Treat this workflow as the default engineering quality gate for ordinary coding tasks once installed. Do not require the user to say `Use gemini-and-chatgpt`.

Core rule:

> AI reasons. Deterministic components enforce lifecycle, evidence, exact code identity, review limits, and release gates.

Antigravity/Gemini is the implementation/orchestration authority. ChatGPT Web is an independent reviewer of the exact delivered code. Human release/safety authority is never bypassed.

## Automatic activation

The installer writes a managed block into project-root `AGENTS.md`. That block is the automatic activation layer: implementation, bug-fix, refactor, feature, test, configuration/build, dependency, security, and architecture coding work must enter this workflow without waiting for the user to name the skill.

Do not force slash commands or AWF-style command syntax on the user. Ordinary natural-language coding requests are the primary UX.

## Runtime authority

Use `scripts/orchestrator.py` as the v2 lifecycle entrypoint. Authoritative task state lives under:

```text
.ai/
â”œâ”€â”€ project-context.json
â”œâ”€â”€ active-task.json
â””â”€â”€ tasks/<task-id>/
    â”œâ”€â”€ state.json
    â”œâ”€â”€ plan.json
    â”œâ”€â”€ plan.md
    â”œâ”€â”€ verification.jsonl
    â”œâ”€â”€ review-history.jsonl
    â””â”€â”€ checkpoints/
```

`workflow_state.py` is only a compatibility facade. If an active v2 task exists, it must project/delegate to v2 state rather than create a second authority. `.ai/review-state.json` remains a temporary compatibility boundary for the proven delivery backend.

## Required engineering flow

For normal coding work, minimize external command count. Use `orchestrator.py start` as the normal entrypoint so task creation + deterministic classification/routing happen in one command; do not run separate `init` then `classify` commands on the happy path.

1. `RECEIVED` â€” normalize the requested goal and constraints.
2. `CLASSIFIED` â€” run deterministic task classification/risk routing inside the same `start` call.
3. For non-trivial work (`planner_required` or `architect_required`), ensure `.ai/project-context.json` exists and is `FRESH` using `scripts/project_context_scan.py`; stale discovery must be refreshed before Planner/Architect consumption. SIMPLE work may bypass this scan to preserve proportional overhead.
4. For `SIMPLE`, continue to `IMPLEMENTING` with a minimal task contract.
5. For `STANDARD`, require Planner output and `PLAN_READY` before implementation.
6. For `COMPLEX`, require planning and honor `architect_required`; if architecture/human precheck is required but no dedicated Architect execution exists, fail safely into `HUMAN_DECISION`. Never pretend architecture approval occurred.
7. `IMPLEMENTING` â€” Builder makes the narrow change.
8. Create a dedicated candidate commit and bind `implementation.candidate_sha` to the full 40-character commit SHA.
9. `VERIFYING` â€” use one `orchestrator.py verify` call that binds the candidate SHA and runs the Central Verification Gate; do not run separate `begin-verify` then `verify` commands on the happy path. Required evidence must PASS for that exact candidate SHA.
10. `PR_PREPARING` â€” ensure GitHub auth/remote, push the candidate, and create/update the PR. Do not run a separate `delivery`/`pr_context.py` command on the happy path because `review_round.py` reconciles delivery identity internally.
11. Review is a ONE-SHOT deterministic run: `python .agents/skills/gemini-and-chatgpt/scripts/review_round.py --root .` generates a lightweight, GitHub link-based independent review prompt package (`reviewer-prompt.txt`) containing the user goal, GitHub PR & file diff URLs, verification evidence, and a structured audit checklist (requirements alignment, feature correctness, security audit, and feature recommendations). It performs prompt injection via CDP or Browser Subagent without inlining giant raw diffs, clicks Send once, waits for the response, and records the parsed verdict. Exit code 0 = verdict recorded; exit code 4 = `REVIEWER_LOGIN_REQUIRED` (sign in once in the reviewer window, then rerun the same command); other exits = BLOCKED transport failure.
12. `REQUEST_CHANGES` -> evaluate findings -> `FIXING` -> new candidate -> Verification Gate -> push -> rerun the one-shot `review_round.py` for the new HEAD.
13. `APPROVED_TO_MERGE` -> `RELEASE_GATE`; stop before merge.
14. Human gate, malformed review, material unresolved disagreement, or review round reaches 5 without approval -> stop safely.

Do not merge automatically unless the user explicitly enabled automatic merge for the current repository/task. The default release policy is `human_only`.

## Classification and risk routing

Use `scripts/task_classifier.py`. Keep routing deterministic and explainable.

- `SIMPLE`: low-risk, narrow work; full Planner graph must be omitted. Count only product/source files and components affected by the user's requested change. Do not count GitHub, ChatGPT review, PR delivery, or this workflow's own infrastructure as task components. Example: create one `.txt` file and run the full review workflow is still `SIMPLE`.
- `STANDARD`: Planner required.
- `COMPLEX`: Planner required and `architect_required=true`; hard-risk triggers may also require human precheck.

Human/safety gates include destructive database/data migrations, authentication/authorization, payments, secrets/credentials, production infrastructure, breaking public API/schema changes, irreversible data operations, major dependency migrations, significant concurrency/data-integrity changes, broad cross-service architecture, or unresolved reviewer-builder disagreement.

## Planning

For non-trivial tasks use `scripts/plan_store.py` and `references/roles/planner-contract.md`.

`plan.json` is authoritative; `plan.md` is a deterministic human-readable projection. Plans must use stable work-item IDs, explicit dependencies, acceptance criteria, owner roles, verification requirements, scope/out-of-scope, constraints, assumptions, risk notes, and release constraints. Reject dependency cycles. Do not hard-code a database/backend/frontend phase sequence.

## Builder contract

Read `references/builder-contract.md` before implementation. Do not modify unrelated files, weaken tests, disable security controls, conceal failures, or blindly implement reviewer suggestions.

## Verification Gate

Use `scripts/verification_gate.py` and `references/policies/verification-policy.md`.

Verification authority is bound to one exact full candidate SHA. Evidence is append-only in `verification.jsonl`. Aggregate status is `PASS`, `FAIL`, `BLOCKED`, or `PARTIAL`.

Only `PASS` for the current candidate may authorize `PR_PREPARING`. Required `SKIPPED` is not PASS. Evidence from a previous candidate may remain for audit but has no authority over a new candidate.

**Agent usage for Verification:**
For most tasks (especially SIMPLE), you can run verify without arguments (it will automatically use HEAD and empty checks):
```bash
python .agents/skills/gemini-and-chatgpt/scripts/orchestrator.py verify --root .
```

If specific checks or a specific candidate SHA are required:
```bash
python .agents/skills/gemini-and-chatgpt/scripts/orchestrator.py verify --root . --candidate-sha <FULL_SHA> --checks "check1,check2"
```

## GitHub delivery gate

GitHub is mandatory before ChatGPT review. Before the review phase:

1. work in a Git repository;
2. `git` and `gh` must be available;
3. `gh auth status` must succeed;
4. GitHub `origin` must exist;
5. the task branch must be pushed;
6. a PR must exist and be `OPEN`;
7. `review_round.py` must reconcile full local/PR/base SHAs with `git` + `gh`;
8. exact PR HEAD must equal the verified candidate SHA.

If GitHub auth, `gh`, or `origin` is missing, stop before review and tell the user to rerun `gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat`. Never ask the user to paste a PAT into chat.

A new PR HEAD invalidates any prior approval. Prefix or abbreviated SHA equivalence is forbidden.

## Independent ChatGPT Web review

Read `references/review-contract.md` and `references/policies/review-policy.md` before review.

Keep the user-facing Antigravity conversation in the user's language (Vietnamese when the user is speaking Vietnamese). Keep the Antigravity -> ChatGPT reviewer channel English-only: reviewer instructions, review reasoning, findings, and final machine-parseable verdict must be in English. Source-code identifiers, paths, literals, and quoted task text may remain unchanged when necessary.

The deterministic delivery gate, not ChatGPT Web, is authoritative for GitHub PR identity. `review_round.py` uses `git` + `gh` to establish an OPEN PR and exact full HEAD before prompt generation. The external reviewer may use live GitHub access as optional corroboration, but inability to open a private PR or a 404 caused by reviewer-session permissions is not by itself a reason for `NEEDS_HUMAN_DECISION`. The reviewer must assess the supplied exact-SHA diff/context and verification evidence; escalate only for actual identity inconsistency, materially insufficient evidence, or another substantive blocker.

During workflow/self-validation, treat both `gemini-and-chatgpt/` and `.agents/skills/gemini-and-chatgpt/` as immutable test infrastructure. Do not edit, generate files inside, or patch either copy during validation unless the user explicitly asked to modify the tool. Put proof scripts, temporary fixtures, and evidence outside those tool directories.

Do not open GitHub Web merely to verify PR identity or HEAD, especially for private repositories. The normal path uses `review_round.py`, which performs the deterministic `git` + `gh` reconciliation internally; `scripts/pr_context.py` remains compatibility/diagnostic tooling only. Open a GitHub browser page only when the user explicitly asks for it or when a genuinely browser-only task requires it; a private-repo 404 must not trigger retries or state changes.

The normal path lets `review_round.py` build the concise prompt internally with `review_prompt.py`; do not invoke the prompt builder separately. Include repository/PR identity, exact target HEAD, task goal/scope, acceptance criteria, concise plan, changed-file/implementation context, SHA-bound verification evidence, and relevant prior findings/dispositions. Do not dump project memory, raw chat history, credentials, tokens, or unrelated code.

Use a fresh ChatGPT Web conversation every round. If the HEAD changes, the old approval is invalid.

Normal review execution must be compact. Do not make Antigravity explore helper CLIs, run `--help`, or chain standalone target/readback/attachment verifiers. Once the verified candidate has been pushed and the PR exists, use exactly this command:

```text
python .agents/skills/gemini-and-chatgpt/scripts/review_round.py --root .
```

This one-shot run performs internal packaging, profile locking, CDP transport injection, and verdict parsing. Main Agent does not hand-write `reviewer-response.txt` on the normal path: the one-shot run persists the ChatGPT answer itself, requires the returned `TARGET_HEAD_SHA` to equal the exact current HEAD SHA, verify exact readback/hash/HEAD plus zero attachments/uploads, and fails closed on missing/incomplete responses, corrupt sessions, modified prompts, or SHA mismatch. `scripts/direct_fill_review_prompt.ps1` is the ACTIVE CDP transport invoked internally by `review_round.py` (with the single-flight profile lock); do not run it standalone. Reviewer transport must be clipboard-free and typing-free; it connects to an already-open Antigravity Chrome or dedicated fallback, clicks the Send button directly, and MUST NOT use Windows clipboard. Do not fall back to typing or Shift+Enter unless manual typing fallback is explicitly authorized. Zero attachments/uploads must be used during review.

A Browser Subagent manual-typing fallback exists ONLY when the CDP transport fails AND the user explicitly authorizes manual typing: invoke ONE `browser_subagent` task that opens/reuses `https://chatgpt.com/`, starts a fresh conversation, focuses the composer, enters the COMPLETE prompt from `prompt_path` verbatim using native input actions, verifies both `=== GEMINI_CHATGPT_REVIEW_BEGIN ===` and `=== GEMINI_CHATGPT_REVIEW_END ===` are present in the same draft, clicks the visible Send button exactly once, waits until ChatGPT finishes, and returns the ENTIRE verbatim response. Clipboard is forbidden. Never press bare Enter while composing; use Shift+Enter for line breaks where needed. A partial or early send is `BLOCKED`; never send the remainder as a second message. A failed round is marked BLOCKED and automatic whole-round retry stays suppressed until human authorization via `--retry-blocked`.

Keep normal execution lean: never reread `SKILL.md` after activation, never run helper `--help`, never repeat `git status`/`gh pr view` for reassurance, and never invoke diagnostic Python verifiers after a consolidated step succeeds. Normal lifecycle commands are `orchestrator.py start`, optional Planner/Architect completion only when required, one `orchestrator.py verify`, Git push/PR creation, then one one-shot `review_round.py` run per review round. `orchestrator.py` and `review_round.py` append meaningful actions, command/status, and duration to `.ai/gemini-chatgpt-actions.log` and `.ai/gemini-chatgpt-actions.jsonl`. On failure or final completion, report the action-log path.

The reviewer channel remains English-only. Include the PR URL, repository identity, exact HEAD SHA, user's goal, scope/acceptance criteria, implementation summary, changed-file/diff context, SHA-bound verification evidence, prior finding dispositions, and the review contract. A private GitHub PR returning 404 in the reviewer browser is not a blocker because `gh`/the deterministic delivery gate is authoritative for PR identity.

After `REQUEST_CHANGES`, evaluate findings rather than blindly following them, fix valid blockers, verify the new candidate, push, then rerun the one-shot `review_round.py` for the new HEAD in a fresh review round. Never start round 6: if round 5 still returns `REQUEST_CHANGES`, stop and report remaining blockers. `APPROVED_TO_MERGE` transitions to `RELEASE_GATE`; automatic merge remains OFF unless the user explicitly enabled it.

For Project Context v2 on `STANDARD` and `COMPLEX` tasks, use `scripts/project_context_scan.py` to maintain one durable `.ai/project-context.json`. The scanner must discover only bounded, normalized repository facts: project/repository identity, language/stack indicators, package managers/frameworks, test/lint/typecheck/build/install commands, key module topology, lightweight conventions, and environment **variable names only**. Never persist `.env` values, tokens, passwords, cookies, credential-bearing URLs, or raw chat history. The scanner must ignore `.git/`, `.ai/`, `.agents/`, dependency/build caches, and both `gemini-and-chatgpt/` tool copies.

Every discovered fact must carry provenance through manifest/source paths and the `discovery.sources` ledger. Before reusing context, run freshness checking; changed/missing/new provenance marks the context `STALE`. Refresh stale context before Planner/Architect/Builder consumption rather than silently trusting it. `orchestrator.py classify` automatically ensures fresh context for planned/architectural work, and `resume` refreshes stale discovery before continuation.

Use lazy role-scoped context slices and lazy context slices instead of dumping the entire project context into every role. Do NOT read `.ai/project-context.json` directly. Instead, run `python scripts/orchestrator.py role-context --role <role>` (where role is planner, architect, builder, or verifier) to retrieve the precise slice of context permitted for that role. For the builder, append `--work-item '<keywords>'` to rank module relevance.
