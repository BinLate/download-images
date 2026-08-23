# External MVP Validation Report — 2026-08-19

## Verdict
`EXTERNAL_MVP_VALIDATION_PASS`

The Windows + Antigravity + GitHub CLI + ChatGPT Web external MVP validation is complete for the current canonical build. Gate G reached `RELEASE_GATE` on the exact PR HEAD, the workflow stopped before merge under `human_only`, and the post-Gate-G reviewer transport hardening also passed a live negative screenshot/attachment smoke test.

No REQUIRED external validation item remains blocked for MVP 1.

## Preflight results
- `git`: PASS — `git version 2.47.3`
- current runtime copy is a Git repository: BLOCKED — no `.git` repository present
- `gh`: BLOCKED — command not installed
- Windows `cmd.exe`: BLOCKED — unavailable
- Windows PowerShell / `pwsh`: BLOCKED — unavailable
- interactive Antigravity desktop session: BLOCKED — unavailable to this runtime
- authenticated interactive ChatGPT Web session for the required reviewer workflow: BLOCKED — unavailable to this runtime

## Internal evidence re-run
- `python -m unittest discover -s tests -v`: `76/76 PASS` after reviewer transport hardening
- `python -m py_compile scripts/*.py tests/*.py`: PASS
- focused B8 activation/installer + internal MVP E2E: `9/9 PASS`

## External checks not executed
Do not record these as PASS from this runtime:
- actual BAT execution under Windows `cmd.exe`;
- actual managed AGENTS update under Windows PowerShell;
- real Antigravity natural-language activation after reload;
- real `gh auth status`, push, PR creation/update, and OPEN/head reconciliation;
- real fresh ChatGPT Web independent review of an exact PR HEAD;
- real REQUEST_CHANGES -> fix -> new pushed HEAD -> fresh reviewer conversation loop;
- final human-only release-gate confirmation on Windows.

## Next action
Run `docs/external-mvp-validation-checklist.md` on the Windows Antigravity workstation against a disposable GitHub repository and capture evidence. Replace this verdict only after every REQUIRED item passes.


## Post-validation transport bug fix

During Gate E, external validation exposed a clipboard race condition: unrelated user clipboard activity could replace `reviewer-prompt.txt` between copy and browser paste, and simulated typing could partially submit multiline content. The canonical fix now uses a deterministic transport handshake:

1. `review_prompt.py` emits BEGIN/END markers plus matching `PROMPT_ID` and full `TARGET_HEAD_SHA` at both boundaries.
2. `copy_review_prompt.ps1` copies and reads the Windows clipboard back, requiring exact normalized equality before browser insertion.
3. Antigravity pastes or direct-fills once, reads the entire ChatGPT composer into `reviewer-composer.txt`, and runs `verify_review_transport.py` against `reviewer-prompt.txt`.
4. Only verifier exit code 0 authorizes Send. Mismatch triggers clear -> recopy -> reinsert -> reread -> reverify, up to 3 attempts; then stop.
5. Simulated typing is disabled by default and is not an automatic fallback.

Regression includes the observed race condition, truncated/partially submitted prompt, changed middle content, wrong `PROMPT_ID`, and wrong HEAD. All fail closed. Gate E must be re-run after reinstalling/refreshing the project-local skill. Existing Gate A installer evidence remains useful, but the installed skill must be refreshed before continuing. Current external verdict remains `EXTERNAL_MVP_VALIDATION_BLOCKED` until the corrected Gate E-G flow is validated.


## Post-validation paste-target/focus bug fix

A second Gate E test copied a ChatGPT conversation URL while Antigravity was preparing browser transport. The browser then navigated to that copied URL, demonstrating that clipboard integrity alone was insufficient when global keyboard focus could be outside the composer. The canonical hotfix adds `verify_review_target.py` and requires exact reviewer URL + `document.hasFocus()` + visible/enabled exact composer + `document.activeElement === composer` immediately before insertion and again before Send. Direct DOM fill is preferred; `Ctrl+V` is only allowed with uninterrupted verified composer focus. Address-bar/browser-chrome focus, URL drift, or any other target mismatch fails closed. Gate E must be rerun after refresh.


## Gate E long-running browser-loop hotfix

A real Windows validation run later showed Gate E could continue browser automation for more than one hour even though `target-before-result.json` passed (`page_url=https://chatgpt.com/`, `document_has_focus=true`, `active_is_composer=true`). The runtime is now instrumented and bounded:

- `scripts/review_runtime_log.py` writes append-only `review-runtime.jsonl` and bounded timer state in `review-runtime-state.json`.
- Default hard limits: Gate E 900s overall; normal browser phase 120s; reviewer-response wait 300s; transport attempts 3.
- Every target/clipboard/insert/readback/transport/final-target/send/wait phase must log start/result and check limits before retry/poll.
- Timeout or attempt-limit ends the round `BLOCKED`; indefinite screenshot/DOM/poll loops are forbidden.
- Diagnostic bundle can be generated with `review_runtime_log.py ... summary --tail 40 > review-runtime-summary.json` and sent for analysis without exposing cookies/tokens.

Gate E must be rerun after refreshing the installed skill. Current external verdict remains `EXTERNAL_MVP_VALIDATION_BLOCKED`.

## 2026-08-20 Gate E finding and protocol correction

Gate E transport/runtime controls passed on Windows. The reviewer returned `NEEDS_HUMAN_DECISION` for target `c726754cd00e970b879864894c7d6820d8b1604f` because its browser session could not open the private GitHub PR. This exposed a reviewer-contract issue rather than a code-identity failure: exact PR identity is already established by the deterministic delivery gate before prompt generation.

The canonical protocol is now corrected so that:
- user-facing Antigravity communication stays in the user's language (Vietnamese for this validation);
- the Antigravity <-> ChatGPT Web reviewer channel is English-only;
- private-PR browser inaccessibility/404 is not by itself a reason for `NEEDS_HUMAN_DECISION` when the exact-SHA package, diff/context, and verification evidence are internally consistent;
- actual SHA inconsistency, insufficient evidence, or substantive blockers still fail closed.

The previous `NEEDS_HUMAN_DECISION` verdict is not converted into approval retroactively. Re-run a fresh review round with the corrected protocol before any release-gate conclusion.


## Final Gate G result

External validation reached `RELEASE_GATE` on PR #1 at exact HEAD `c726754cd00e970b879864894c7d6820d8b1604f`. Fresh reviewer round 3 returned `APPROVED_TO_MERGE`, no blocking findings, no test gaps, and `PRODUCTION_READINESS: PASS`. The workflow stopped before merge under `human_only`, so the end-to-end MVP release gate is externally validated.


## Post-validation transport smoke — COMPLETE

A fresh review round was executed on the unchanged approved PR HEAD using the final transport build. The atomic clipboard path, exact composer readback verification, final target verification, attachment-aware pre-Send guard, and no-simulated-typing policy all passed externally.

### 2026-08-20 attachment-race finding — RESOLVED
The atomic clipboard smoke test exposed a failure mode where a user screenshot could become an attachment while exact reviewer text was later inserted. The final build added `verify_review_attachments.py` and a fail-closed pre-Send attachment gate.

Live negative smoke evidence on the current build:
- clipboard fallback path exercised on the unchanged approved PR HEAD `c726754cd00e970b879864894c7d6820d8b1604f`;
- non-zero attachment state was detected before Send;
- the draft was converted/cleaned until `attachment_count=0`, `pending_upload_count=0`, no preview/remove control, no pending upload, and no upload error remained;
- exact composer text read-back matched `reviewer-prompt.txt` with the expected `PROMPT_ID` and exact HEAD SHA;
- target verification passed before insertion and before Send;
- ChatGPT returned `APPROVED_TO_MERGE` for the same exact HEAD;
- candidate code remained untouched and no merge was executed.

This closes the final post-validation transport requirement. Final verdict: `EXTERNAL_MVP_VALIDATION_PASS`.
