# Review Policy — Exact-SHA Independent Review

## Identity boundary

Every external review is bound to one exact Git commit: the current open pull request HEAD. The review target must be exactly 40 hexadecimal characters and must equal all of:

- `delivery.head_sha`;
- `review.current_target_sha`;
- `verification.candidate_sha`.

Abbreviated SHAs and prefix equivalence are forbidden.

## Fresh reviewer context

Every review round uses a fresh ChatGPT Web conversation. Prior reviewer conversation state is not an authority. Relevant prior findings and dispositions are projected into the new review package explicitly.

## Evidence boundary

Review may begin only after the Central Verification Gate reports `PASS` for the exact current candidate SHA. The review package includes concise evidence bound to that SHA, not an unbounded project-memory or chat transcript dump.

## Changed HEAD invalidation

When a new HEAD is pushed, any prior approval becomes non-authoritative immediately:

```text
approval_valid = false
current_verdict = null
current_target_sha = new_head
release.approved_sha = null
```

The new HEAD must pass verification and receive a fresh independent review.

## Review limit

The default and maximum automated review budget remains five rounds for the workflow. A fifth round that still returns `REQUEST_CHANGES` stops at `REVIEW_LIMIT_REACHED`; automation must not silently begin round six.

## Fail closed

Missing, malformed, abbreviated, stale, or mismatched review identity is never guessed. It routes to parser failure / `NEEDS_HUMAN_DECISION` as appropriate.
