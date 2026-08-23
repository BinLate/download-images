# Delivery Gate Contract — MVP 1

Delivery connects the verified candidate commit to GitHub and the independent reviewer.

## Required identity

Before `REVIEWING`:

- verification status is `PASS`;
- verification candidate SHA is a full 40-character SHA;
- PR state is `OPEN`;
- PR number and URL are known;
- PR HEAD SHA is a full 40-character SHA;
- PR HEAD equals the verified candidate SHA exactly.

If any identity changes, prior review approval is invalidated.

## Compatibility boundary

B6 continues to reuse `pr_context.py`, GitHub CLI, the existing clipboard/browser workflow, and `parse_review.py`. Exact-SHA parser hardening and enriched review prompts remain B7 work.

## Release boundary

`APPROVED_TO_MERGE` for the exact current HEAD moves the task only to `RELEASE_GATE`. Automatic merge remains disabled unless explicitly enabled later by repository/task policy and human authority.
