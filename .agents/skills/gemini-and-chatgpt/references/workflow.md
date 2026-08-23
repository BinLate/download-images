# Workflow Reference

## Overview

GitHub is the shared state bus. The builder changes code; CI produces executable evidence; ChatGPT Web reviews a specific immutable HEAD SHA; the orchestrator decides whether to repair, escalate, or stop.

## Recommended repository-local state

Store ephemeral state at `.ai/review-state.json`:

```json
{
  "task_id": "TASK-001",
  "state": "REVIEWING",
  "review_round": 2,
  "max_review_rounds": 5,
  "pr_number": 123,
  "pr_url": "https://github.com/owner/repo/pull/123",
  "base_sha": "...",
  "head_sha": "...",
  "ci": "PASS",
  "review": "REQUEST_CHANGES"
}
```

Use `.git/info/exclude` if the file should remain local.

## Initialization

```bash
python scripts/workflow_state.py init --task TASK-001 --max-rounds 5 --file .ai/review-state.json
```

Inspect:

```bash
python scripts/workflow_state.py show --file .ai/review-state.json
```

Update phase:

```bash
python scripts/workflow_state.py set --file .ai/review-state.json --state VERIFYING
```

Increment review round only after a new HEAD has been pushed and is ready for another independent review:

```bash
python scripts/workflow_state.py next-round --file .ai/review-state.json
```

## Project Context v2 gate

For non-trivial tasks, maintain `.ai/project-context.json` with `scripts/project_context_scan.py`. The context is repository-derived evidence, not model memory. Scan before Planner/Architect work when missing; run freshness checks before reuse; refresh if any provenance source changed, disappeared, or a new root manifest appeared. SIMPLE tasks may skip the scan.

Discovery must be bounded and secret-safe. Ignore `.git/`, `.ai/`, `.agents/`, dependency/build/cache directories, and both project-local/installed `gemini-and-chatgpt` tool copies. Read safe manifests/configuration only; `.env.example`/sample/template files may contribute variable **names**, never values. Persist stack/command/module facts with provenance and a SHA-256 source fingerprint.

Do not pass the full context to every role. Request only the topic needed for the current step (`commands`, `stack`, `modules`, `architecture`, `conventions`, `known_risks`, or `environment`). A stale context cannot authorize a role package; refresh it first.


## Minimal normal command path

Do not decompose normal work into many tiny CLI calls. Use these consolidated boundaries:

1. `python .agents/skills/gemini-and-chatgpt/scripts/orchestrator.py start ...` — create task + classify/route once. A one-file low-risk change must remain SIMPLE; workflow/PR/reviewer infrastructure does not count as product scope.
2. Planner/Architect commands only if classification actually requires them.
3. After implementation and candidate commit, `python .agents/skills/gemini-and-chatgpt/scripts/orchestrator.py verify ...` — bind candidate + run required checks once.
4. Push branch and create/update PR with Git/`gh`.
5. Run `python .agents/skills/gemini-and-chatgpt/scripts/review_round.py --root .` to automatically generate the lightweight, GitHub link-based review prompt (`reviewer-prompt.txt`), perform one-shot prompt submission to ChatGPT Web, collect the verdict, and update the lifecycle state to `RELEASE_GATE` or `FIXING`.

Do not run `--help`, standalone `pr_context.py`, `begin-verify`, `delivery`, reviewer verifier scripts, or repeated state checks on a successful happy path. `.ai/gemini-chatgpt-actions.log` is the compact diagnostic record; logging is in-process and adds no extra shell commands.

## GitHub connection gate

Before any ChatGPT review, require all GitHub prerequisites to be real, not assumed:

1. `gh auth status` succeeds.
2. `git remote get-url origin` succeeds and points to the intended GitHub repository.
3. The implementation is committed on a task branch and pushed to `origin`.
4. A Pull Request exists for that branch.
5. The exact current PR HEAD SHA is known.

If authentication or `origin` is missing, stop and tell the user to rerun `gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat`. The installer offers browser/PAT login and repository creation/connection. Never skip GitHub and jump directly to ChatGPT Web.

## GitHub PR context

The normal review path does not require a separate PR-context command. After the PR exists and the branch is pushed, `review_round.py` calls `git` + `gh` internally, requires the PR to be OPEN, and requires exact equality of local HEAD, PR HEAD, and the Verification Gate candidate SHA. `scripts/pr_context.py` is retained only for compatibility/diagnostics. Do not navigate to GitHub Web solely to verify these facts. Private-repository browser 404s are not validation failures.

## Review round

The review package is lightweight (~8 KB) and link-based:

```bash
# One-shot invocation:
python .agents/skills/gemini-and-chatgpt/scripts/review_round.py --root .
```

`review_round.py` performs these deterministic steps:

1. Accept only `PR_PREPARING` or resumable `REVIEWING`.
2. Use `git` + `gh` to require an OPEN PR and exact equality of local HEAD, PR HEAD, and verified candidate SHA.
3. Sync delivery/enter `REVIEWING` when needed.
4. Save the full diff to `pr-diff.patch`.
5. Build the lightweight, link-based `reviewer-prompt.txt` directing ChatGPT to inspect the GitHub PR/branch files for goals, correctness, security, and suggestions.
6. Submit the prompt, collect the response, and parse the verdict.

### Browser Subagent ownership and multiline safety

Main Agent reads the COMPLETE UTF-8 `reviewer-prompt.txt` with `view_file` before invoking Browser Subagent and passes that complete text verbatim in one Browser Subagent task. The Browser Subagent owns the entire browser interaction through completion: open/reuse `https://chatgpt.com/`, start a fresh chat, focus the composer, enter the complete prompt with the native input actions actually available in the runtime, verify both BEGIN and END markers exist in the same draft, click the visible Send button exactly once, wait for ChatGPT to finish, and return the entire verbatim response.

Do not use clipboard. Never press bare Enter while the prompt is still being composed; if a keystroke-oriented native tool requires explicit line breaks, use Shift+Enter. If the complete prompt is already present in the composer, verify both markers and click Send rather than retyping it. A partial or early send is `BLOCKED`; do not send the remainder as a second message. Browser Subagent must not return merely because the draft is filled.

There is no active `transport` phase and no OS-level CDP/PowerShell browser handoff on the happy path. `scripts/direct_fill_review_prompt.ps1` is legacy-disabled compatibility code only.

`finalize` performs these deterministic steps:

1. Reconcile OPEN PR/local/verified HEAD again so a changed HEAD invalidates the pending review.
11. **Browser Review Subagent**: Main Agent reads `prompt_path` and delegates ONE browser session to Antigravity Browser Subagent to open `chatgpt.com`, type the prompt into the DOM, verify markers, require exact text/hash equality and zero attachments/uploads, check for zero attachments/pending uploads, Click the ChatGPT Send button through the DOM, wait, and return the response. No PowerShell, no clipboard.
12. **Finalize**: Run `review_round.py finalize` which parses the verdict and requires returned `TARGET_HEAD_SHA` to match PR HEAD exactly.
6. Record the verdict and lifecycle transition.

Round artifacts are kept out of the repository root:

```text
.ai/tasks/<task-id>/reviews/round-XX/
  pr-diff.patch
  reviewer-prompt.txt
  reviewer-prompt.manifest.json
  review-session.json
  reviewer-response.txt
  review-result.json
```

`scripts/direct_fill_review_prompt.ps1` is retained only as a fail-closed legacy compatibility stub and must not run on the normal path. Python owns deterministic identity/package/verdict gates; Antigravity Browser Subagent owns the browser interaction.

Normal execution must not run helper `--help`, repeated state-inspection commands, or standalone reviewer verifier scripts after a consolidated step succeeds. `orchestrator.py` and `review_round.py` write `.ai/gemini-chatgpt-actions.log` and `.ai/gemini-chatgpt-actions.jsonl` in-process.

## Suggested GitHub commands

Create branch:

```bash
git switch -c ai/task-short-name
```

Commit:

```bash
git add -- <intended-files>
git commit -m "feat: implement task"
```

Push:

```bash
git push -u origin HEAD
```

Create PR:

```bash
gh pr create --fill
```

Inspect PR:

```bash
gh pr view --json number,url,headRefName,headRefOid,baseRefName,baseRefOid,state,statusCheckRollup
```

Diagnostic-only PR diff inspection (not part of the normal review path):

```bash
gh pr diff
```

The normal `review_round.py` path already has exact base/head SHAs from `gh pr view` and builds the review diff locally with `git diff`; do not run this command for reassurance.

## Review limit

Default `max_review_rounds` is 5. If round 5 still returns `REQUEST_CHANGES`, do not start round 6. Escalate with a compact summary of remaining blockers and disagreements.

## Failure and recovery

## Validation isolation

When validating this workflow itself, do not modify either `gemini-and-chatgpt/` or `.agents/skills/gemini-and-chatgpt/`. They are test infrastructure, not the validation target. Put proof scripts, fixtures, generated application modules, coverage files, and evidence in the disposable project workspace or `.ai/`. If a validation scenario appears to require changing the tool, stop and report the gap instead of self-patching the installed/source Skill.

## Review transport and zero-attachment verification
The review workflow executes `review_round.py --root .` to connect to an already-open Antigravity Chrome or fallback instance. No typed fallback is permitted on the happy path. The transport checks that there are zero attachments/pending uploads before submission, and must require exact text/hash equality and zero attachments/uploads before sending. Click the ChatGPT Send button through the DOM and Wait at most 300 seconds for completed response.

If a script reports a HEAD mismatch, treat all prior approval as stale. Start a fresh review for the new HEAD.

If CI changes from green to red after review, approval is insufficient; return to verification.

## Review-round idempotency and retry safety

- If lifecycle is already `RELEASE_GATE` and the approved SHA still equals local/PR HEAD, `review_round.py` returns `ALREADY_APPROVED` and performs no browser review.
- Re-running `prepare` for the same still-current round regenerates the deterministic package/session and clears stale response artifacts.
- `finalize` rechecks PR/local/verified HEAD and the immutable session before accepting a response, so a changed HEAD or stale response fails closed.
- Never create scratch browser tests or edit the Skill copies to diagnose a normal task. Use `.ai/gemini-chatgpt-actions.log` as the diagnostic source.
