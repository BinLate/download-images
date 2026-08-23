# Safety and Release Policy

Independent reviewer approval is necessary but not sufficient to merge.

`APPROVED_TO_MERGE` is valid only for the exact current PR HEAD and only while `approval_valid=true`. A code-changing push invalidates the approval. The workflow then requires a new candidate commit, Central Verification Gate PASS, exact PR HEAD reconciliation, and a fresh review round.

The default merge policy is `human_only`. The system stops at the release gate and never auto-merges by default.

Human authority is required for configured safety gates, unresolved reviewer/builder disagreement, exhausted review rounds, malformed review output, stale delivery identity, destructive or credential-sensitive operations, and any condition where the workflow cannot establish exact current repository identity.

Secrets, cookies, tokens, browser credentials, and raw authentication material must never be placed in reviewer prompts, state files, evidence ledgers, or persisted project context.
