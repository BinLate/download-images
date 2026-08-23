# MVP 1 External Validation Checklist

Date: 2026-08-19
Target: Windows + Google Antigravity + GitHub CLI + authenticated ChatGPT Web
Canonical source: `My Drive\Vibe-Code\awf-plus\gemini-and-chatgpt`

## Validation rule
Do not mark the MVP production-validated unless every REQUIRED item below is PASS with captured evidence. Never substitute a simulated result for a missing Windows, GitHub, or ChatGPT Web check.

## A. Windows installer / activation
1. Copy canonical `gemini-and-chatgpt` into a disposable Windows test project root.
2. Confirm `git --version`, `gh --version`, and `gh auth status`.
3. Run `gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat` from outside `.agents\skills\gemini-and-chatgpt`.
4. Verify every Yes/No prompt displays `(default Y)` / `(default N)` and Enter follows that default.
5. Confirm no BAT parse error.
6. Confirm exactly one installed skill at `<project>\.agents\skills\gemini-and-chatgpt\`.
7. Confirm installed copy includes `SKILL.md`, `scripts\`, `references\`, `schemas\`, and `agents\openai.yaml`.
8. Confirm project-root `AGENTS.md` contains exactly one managed gemini-and-chatgpt block.
9. Run installer again and confirm idempotency plus stale-file clean refresh.
10. Reload/reopen Antigravity.

Required evidence: console transcript/screenshot, installed tree, managed AGENTS block, redacted `gh auth status` output.

## B. Natural-language auto activation
1. Do not mention the skill name or a slash command.
2. Submit a low-risk SIMPLE coding task in ordinary language.
3. Confirm automatic workflow activation.
4. Submit a STANDARD multi-file task and confirm planning before implementation.
5. Submit a safe high-risk test prompt and confirm it routes to human precheck without destructive execution.

## C. Verification and candidate identity
1. Complete one disposable implementation task.
2. Create a dedicated branch and candidate commit.
3. Run applicable lint/typecheck/focused tests/build/smoke checks.
4. Confirm evidence is append-only and bound to the exact full 40-character candidate SHA.
5. Confirm required failed/skipped checks cannot authorize PR preparation.
6. Create a new candidate SHA and confirm old PASS evidence cannot authorize it.

## D. GitHub PR identity
1. Push the candidate branch and create/update a PR.
2. Run `python scripts/pr_context.py --write .ai/review-state.json` from the installed workflow.
3. Confirm PR state `OPEN`.
4. Confirm local HEAD == PR HEAD and both are full 40-character SHAs.
5. Confirm CLOSED/MERGED PR is rejected.
6. Confirm abbreviated SHA is rejected.

## E. ChatGPT Web independent review
1. Open a fresh ChatGPT Web conversation for round 1.
2. Generate the reviewer prompt for the exact current task/PR state.
3. Confirm it contains repo/PR identity, exact target HEAD SHA, goal/scope, acceptance, concise plan, verification evidence, and reviewer contract.
4. Confirm it excludes secrets, cookies, tokens, and unrelated memory.
5. Review the exact PR HEAD.
6. Save reviewer response and parse with `scripts/parse_review.py` against the exact expected HEAD.
7. Confirm malformed output and wrong SHA fail closed.

## F. REQUEST_CHANGES loop
1. Obtain a legitimate non-destructive `REQUEST_CHANGES` round or use a controlled validation task designed to surface a real finding.
2. Builder evaluates findings; never apply blindly.
3. Fix accepted findings, reverify, commit, and push a new HEAD.
4. Confirm old approval/verdict has no authority over the new HEAD.
5. Confirm review round increments only when entering a fresh review of the reconciled new PR HEAD.
6. Open a new ChatGPT Web conversation for the new round.

## G. Approval / release gate
1. Obtain `APPROVED_TO_MERGE` for the exact current PR HEAD.
2. Confirm required verification is PASS for the same SHA.
3. Confirm no unresolved blocker/human gate.
4. Confirm workflow stops at `RELEASE_GATE`.
5. Confirm no automatic merge occurs by default.

## H. Recovery
1. Stop/restart Antigravity during a non-terminal task.
2. Resume persistent task state.
3. Reconcile real Git/PR HEAD before resuming review.
4. Confirm stale/corrupt state fails closed.

## Final sign-off
Record Windows version, Antigravity version, Git/GH versions, repository/PR, final HEAD SHA, review rounds, final verdict, and PASS/FAIL for installer, activation, verification, GitHub identity, ChatGPT review, recovery, and human-only release gate.

Final verdict must be exactly one of:
- `EXTERNAL_MVP_VALIDATION_PASS`
- `EXTERNAL_MVP_VALIDATION_FAIL`
- `EXTERNAL_MVP_VALIDATION_BLOCKED`


## Gate E runtime observability / timeout evidence (REQUIRED)

Before browser review, start `scripts/review_runtime_log.py` and preserve `review-runtime.jsonl` + `review-runtime-state.json`. Required limits: Gate E <= 900s overall, normal browser phase <= 120s, reviewer-response wait <= 300s, transport attempts <= 3. Timeout/retry exhaustion must produce `BLOCKED`, never an unbounded browser loop. For diagnosis, generate `review-runtime-summary.json` with the logger `summary --tail 40` command and attach it to the validation evidence.


## Executed result — 2026-08-20

`EXTERNAL_MVP_VALIDATION_PASS`

Final evidence summary:
- Windows installer / activation: PASS.
- Natural-language auto activation: PASS.
- Verification + exact candidate identity: PASS.
- GitHub OPEN PR + exact full HEAD reconciliation: PASS.
- ChatGPT Web independent review: PASS.
- Reviewer transport target/focus, runtime timeout, English-only review protocol, and exact text read-back: PASS.
- Approval / human-only release gate: PASS at PR #1 exact HEAD `c726754cd00e970b879864894c7d6820d8b1604f`; no automatic merge occurred.
- Final negative screenshot/attachment smoke: PASS. A non-zero attachment state was detected before Send, cleaned/converted to zero attachments and zero pending uploads, then text + target + attachment checks all passed before the review was sent.

### Final transport smoke addendum — attachment guard
- REQUIRED: after insertion and immediately before Send, `verify_review_attachments.py` reports zero attachments and zero pending uploads. — PASS
- REQUIRED negative test: copying a screenshot/image during clipboard fallback must never result in a sent review message containing that image. If an attachment appears in the draft, automation must clean/convert the draft, reverify attachment state, reverify exact text, and only then Send. — PASS
