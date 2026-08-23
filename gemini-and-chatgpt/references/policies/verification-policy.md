# Verification Policy — MVP 1

## Identity rule

Verification is valid only for one immutable candidate commit. Every evidence record and the task verification summary must contain the exact full 40-character candidate SHA. A code-changing commit invalidates the authority of earlier PASS evidence for delivery.

## Evidence ledger

Store append-only evidence at:

```text
.ai/tasks/<task-id>/verification.jsonl
```

Each line is one `verification-evidence.schema.json` record. Keep summaries concise; do not copy large logs or secrets into task state.

## Check categories

- `LINT`
- `TYPECHECK`
- `FOCUSED_TEST`
- `REGRESSION_TEST`
- `BUILD`
- `INTEGRATION_SMOKE`
- `CUSTOM`

## MVP tier defaults

`SIMPLE`: tests are required; lint/build run when configured or explicitly required by the task.

`STANDARD`: tests, lint, and build are required when the policy resolves them as required.

`COMPLEX` or high-risk: tests plus applicable lint/typecheck/build are required. Project/task-specific migration, security, or integration checks should be supplied explicitly as `CUSTOM` or `INTEGRATION_SMOKE` checks until richer policy routing is added.

## Fail-closed rules

- Required `FAIL` => aggregate `FAIL`.
- Required `BLOCKED` => aggregate `BLOCKED`.
- Required `SKIPPED` => aggregate `PARTIAL`; it cannot become PASS automatically.
- Optional non-passing evidence => aggregate `PARTIAL` rather than hiding it under PASS.
- No evidence => not PASS.
- Evidence whose SHA differs from the candidate SHA is invalid.
- Candidate SHA differing from `implementation.candidate_sha` is rejected unless implementation has not yet recorded a candidate; in that case the gate records it.

## Repair loop boundary

A failed local verification sends work back to implementation/fixing. Local repair attempts are separate from the maximum five external ChatGPT review rounds. B5 records and gates verification; orchestration/retry policy is connected later in B6.
