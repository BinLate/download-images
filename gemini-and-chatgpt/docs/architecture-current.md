\# Current Architecture Audit — gemini-and-chatgpt

Date: 2026-08-19  
Canonical source: \`My Drive\\Vibe-Code\\awf-plus\\gemini-and-chatgpt\`  
Status: Baseline audit only; no AWF integration or behavior change in this step.

\#\# 1\. Purpose and core architecture

\`gemini-and-chatgpt\` is currently a repository-local Antigravity quality gate. Antigravity/Gemini owns planning, implementation, verification, Git/GitHub operations, and repair work. ChatGPT Web is a separate independent reviewer and release gate. GitHub PR state and the exact PR HEAD SHA are the shared source of truth between builder and reviewer.

The operational chain is:

\`TASK\_RECEIVED \-\> PLANNING \-\> IMPLEMENTING \-\> VERIFYING \-\> CREATE\_OR\_UPDATE\_PR \-\> REVIEWING \-\> (FIXING \-\> VERIFYING \-\> new HEAD \-\> REVIEWING)\* \-\> RELEASE\_GATE \-\> APPROVED/HUMAN\_DECISION\`

The review loop is capped at 5 rounds by default and automatic merge is OFF unless explicitly enabled by the user.

\#\# 2\. Canonical top-level structure observed

The canonical Drive folder currently exposes:

\- \`README.md\`  
\- \`SKILL.md\`  
\- \`scripts/\`  
\- \`references/\`  
\- \`agents/\`  
\- \`docs/\` (created for architecture audit documents)

Important integrity finding: the canonical folder does NOT currently expose \`INSTALL-ANTIGRAVITY.bat\`, while another older/parallel \`gemini-and-chatgpt\` folder on Drive does contain it. Because the canonical source has been explicitly defined as \`awf-plus\\gemini-and-chatgpt\`, this mismatch is recorded as a P0 source-integrity gap. No file was copied from the older folder during this audit.

\#\# 3\. Control plane

\#\#\# \`SKILL.md\`

\`SKILL.md\` is the primary behavioral control plane. It defines prerequisites, the default workflow states, builder/reviewer separation, GitHub gating, exact-SHA review, review parsing, handling of findings, stop conditions, recovery behavior, and browser constraints.

Key invariants already encoded:

1\. Normal coding requests should trigger the workflow without requiring the user to name the skill.  
2\. GitHub must be ready before ChatGPT review starts.  
3\. A PR must exist and its current exact HEAD SHA must be known.  
4\. Every new pushed HEAD invalidates prior approval.  
5\. Reviewer output is parsed into only three accepted verdicts: \`APPROVED\_TO\_MERGE\`, \`REQUEST\_CHANGES\`, \`NEEDS\_HUMAN\_DECISION\`.  
6\. Builder evaluates reviewer findings rather than blindly applying them.  
7\. Review round limit defaults to 5\.  
8\. Auto-merge remains OFF by default.

\#\#\# \`AGENTS.md\` activation layer

\`scripts/install\_agents\_rule.ps1\` maintains a marked block in project-root \`AGENTS.md\` and migrates an older \`ai-pr-review-loop\` block name to the current \`gemini-and-chatgpt\` block. This is the persistent auto-activation layer: ordinary implementation, bug-fix, refactor, or feature work should automatically apply the installed skill.

The script also enforces the order: local verification \-\> GitHub auth/origin \-\> branch commit/push \-\> PR \-\> exact HEAD SHA \-\> ChatGPT Web review. It specifies clipboard-based prompt paste as the preferred browser interaction and keeps auto-merge disabled by default.

\#\# 4\. Reference contracts

\#\#\# \`references/builder-contract.md\`

Defines the implementation-engineer role. It requires minimal scoped changes, preservation of architecture unless justified, no unrelated edits, no weakening of tests/security/CI, test additions where feasible, failure diagnosis, secret hygiene, staged-diff checks, and evidence-based treatment of reviewer findings.

Finding dispositions are explicit:

\- \`ACCEPT\_FINDING\`  
\- \`REJECT\_FINDING\_WITH\_EVIDENCE\`  
\- \`NEEDS\_HUMAN\_DECISION\`

\#\#\# \`references/review-contract.md\`

Defines ChatGPT Web as an independent senior reviewer/release gate. It binds review scope to \`TARGET\_HEAD\_SHA\`, defines review areas and severity, prohibits unsupported requirements/style churn, and requires a structured final response containing target SHA, verdict, blocking/non-blocking findings, test gaps, security result, and production-readiness result.

\#\#\# \`references/workflow.md\`

Documents GitHub as the shared state bus, \`.ai/review-state.json\` as repository-local ephemeral workflow state, GitHub prerequisites, PR context acquisition, review-round mechanics, review limit, and recovery behavior.

\#\#\# \`references/installation.md\`

Documents the intended one-click project-local installation model and GitHub/ChatGPT prerequisites.

\#\# 5\. Runtime scripts

\#\#\# \`scripts/workflow\_state.py\`

Purpose: local workflow-state persistence.

Supported states:

\- \`TASK\_RECEIVED\`  
\- \`PLANNING\`  
\- \`IMPLEMENTING\`  
\- \`VERIFYING\`  
\- \`CREATE\_OR\_UPDATE\_PR\`  
\- \`REVIEWING\`  
\- \`FIXING\`  
\- \`RELEASE\_GATE\`  
\- \`APPROVED\`  
\- \`HUMAN\_DECISION\`  
\- \`FAILED\`

Commands:

\- \`init\`  
\- \`show\`  
\- \`set\`  
\- \`next-round\`

State fields include task id, current state, review round/max rounds, review result, CI result, PR number/URL, base SHA, head SHA, and \`updated\_at\`.

Architectural limitation: transitions are not validated as a graph. Any valid state can be set directly, so the script stores state but does not enforce legal state transitions.

\#\#\# \`scripts/pr\_context.py\`

Purpose: reconcile the local repository with GitHub PR metadata and persist immutable review identity.

It obtains repository identity through \`gh repo view\`, PR metadata through \`gh pr view\`, local HEAD through Git, and fails closed if local HEAD differs from PR HEAD. It writes repository, PR, branch, base/head SHA, PR state, and timestamp into the workflow-state JSON.

Strength: exact local/PR HEAD equality is enforced before review.

Architectural limitation: it assumes \`gh pr view\` can resolve the intended open PR from current context and does not itself own PR creation/update or CI-state collection.

\#\#\# \`scripts/parse\_review.py\`

Purpose: machine-parse ChatGPT reviewer output.

It requires explicit \`TARGET\_HEAD\_SHA\` and one of the three allowed verdicts. Missing/malformed output becomes \`NEEDS\_HUMAN\_DECISION\`. Optional \`--expect-head\` rejects a SHA mismatch.

Architectural limitation: SHA matching permits prefix equivalence for \>=7 characters, while the higher-level architecture describes an exact HEAD SHA invariant. This should be reconciled in a later hardening step.

\#\#\# \`scripts/copy\_review\_prompt.ps1\`

Purpose: deterministic bulk prompt insertion. It reads a complete prompt file, rejects empty content, and puts the full text on the Windows clipboard.

\#\#\# \`scripts/install\_agents\_rule.ps1\`

Purpose: install/update the auto-activation block in root \`AGENTS.md\`. It is idempotent with respect to its marker block, migrates the old marker name, and collapses duplicate canonical blocks.

\#\# 6\. Metadata

\`agents/openai.yaml\` currently contains display metadata only:

\- display name: \`Gemini \+ ChatGPT Review\`  
\- short description: builder \+ GitHub PR \+ CI \+ independent ChatGPT Web review loop

It does not define multi-agent orchestration behavior.

\#\# 7\. Current state/data model

The current state model is review-centric rather than project/team-centric. \`.ai/review-state.json\` primarily represents one task/review lifecycle:

\- task id  
\- workflow state  
\- review round / max rounds  
\- review verdict  
\- CI status  
\- PR identity  
\- base/head SHA  
\- repository metadata after PR-context reconciliation

Missing for the future AI-software-team goal:

\- persistent project context  
\- architecture decisions  
\- requirements/acceptance criteria  
\- task decomposition  
\- agent/role assignments  
\- dependency graph  
\- checkpoints beyond review round  
\- structured QA evidence history  
\- resolved/rejected finding history  
\- session restore metadata

These are candidates for later AWF-informed design, not additions to make during this baseline audit.

\#\# 8\. Current component boundaries

\#\#\# Builder/orchestrator boundary

Antigravity/Gemini owns:

\- planning  
\- implementation  
\- local verification  
\- branch/commit/push  
\- PR creation/update  
\- reviewer-prompt assembly  
\- finding evaluation  
\- fixes and re-verification  
\- workflow-state decisions

\#\#\# GitHub boundary

GitHub provides:

\- repository identity  
\- branch state  
\- PR identity  
\- immutable target HEAD SHA  
\- CI/check evidence when available

\#\#\# Reviewer boundary

ChatGPT Web owns:

\- independent review of the exact target SHA  
\- blocking/non-blocking findings  
\- production-readiness judgment  
\- structured verdict

ChatGPT Web does NOT own implementation decisions.

\#\#\# Human boundary

Human decision is required for high-risk operations, ambiguous/malformed review output, material reviewer-builder disagreement, unresolved failures, credentials/protected interactions, or exhaustion of the review-round limit.

\#\# 9\. Strengths to preserve as invariants

1\. Builder/reviewer separation.  
2\. GitHub PR as shared source of truth.  
3\. Exact current PR HEAD binding for each review round.  
4\. Fresh ChatGPT conversation for each round.  
5\. Fail-closed malformed reviewer output.  
6\. Builder independently validates findings.  
7\. Re-test before pushing fixes.  
8\. Old approval invalidated by a new HEAD.  
9\. Maximum review-round guard.  
10\. Human release/safety gate and auto-merge OFF by default.  
11\. Automatic workspace activation via \`AGENTS.md\` rather than requiring explicit skill invocation.

\#\# 10\. Gaps and risks found

\#\#\# P0 — Canonical source integrity

\`My Drive\\Vibe-Code\\awf-plus\\gemini-and-chatgpt\` currently lacks \`INSTALL-ANTIGRAVITY.bat\`, while another parallel Drive folder contains an installer. The canonical source and historical standalone source must be reconciled deliberately before installer evolution.

\#\#\# P1 — Documentation drift

The canonical README still states the old working source path \`My Drive\\Vibe-Code\\gemini-and-chatgpt\`. The correct canonical path is \`My Drive\\Vibe-Code\\awf-plus\\gemini-and-chatgpt\`.

\#\#\# P1 — State machine is descriptive, not enforced

\`workflow\_state.py\` validates state names but not legal transitions. Recovery and future multi-agent orchestration will need stronger transition/invariant enforcement.

\#\#\# P1 — Review SHA parser accepts abbreviated/prefix-equivalent SHA

\`parse\_review.py \--expect-head\` currently permits prefix matching of at least 7 hexadecimal characters. This is weaker than the stated exact-HEAD contract and should be hardened later.

\#\#\# P1 — State persistence is too narrow for multi-agent evolution

The current JSON is adequate for the PR/review loop but not for persistent project context, decomposed work, role handoffs, checkpoints, or structured QA history.

\#\#\# P2 — Orchestration remains prompt-driven

The skill/reference documents define the workflow well, but no deterministic orchestrator currently enforces the complete lifecycle end-to-end. The current system depends heavily on Antigravity following written instructions correctly.

\#\#\# P2 — CI evidence is mostly declarative

The workflow requires verification evidence, but current helper scripts do not normalize or persist a detailed check/evidence ledger.

\#\# 11\. Current architecture diagram

\`\`\`text  
User task  
   |  
   v  
AGENTS.md auto-activation  
   |  
   v  
SKILL.md control plane  
   |  
   \+--\> builder-contract.md  
   \+--\> workflow.md  
   |  
   v  
Antigravity/Gemini  
PLAN \-\> IMPLEMENT \-\> VERIFY  
   |  
   v  
Git/GitHub CLI  
branch \-\> commit \-\> push \-\> PR  
   |  
   v  
pr\_context.py  
local HEAD \== PR HEAD ?  
   | yes  
   v  
.ai/review-state.json  
   |  
   v  
review prompt \+ review-contract.md  
   |  
   v  
copy\_review\_prompt.ps1 \-\> ChatGPT Web (fresh chat)  
   |  
   v  
reviewer response  
   |  
   v  
parse\_review.py \+ HEAD validation  
   |  
   \+--\> REQUEST\_CHANGES \-\> Gemini evaluates \-\> FIX \-\> VERIFY \-\> PUSH \-\> new HEAD \-\> fresh review  
   |  
   \+--\> NEEDS\_HUMAN\_DECISION \-\> human gate  
   |  
   \+--\> APPROVED\_TO\_MERGE \-\> release gate \-\> STOP before merge by default  
\`\`\`

\#\# 12\. Baseline conclusion

The current project is not yet a multi-agent software team. It is a strong review-centric orchestration protocol with four particularly valuable foundations: automatic activation, builder/reviewer separation, exact-PR-HEAD review discipline, and a fail-closed human release gate.

For AWF integration, the safest architecture is to keep this delivery/review/release half intact and add planning, task decomposition, persistent context, agent contracts, and stronger QA orchestration ahead of it. No AWF subsystem should replace the GitHub/HEAD/reviewer invariants without an explicit architecture decision.

\#\# 13\. Gate status

Bước 01 — Current Architecture Audit: COMPLETE.

No AWF code was integrated and no runtime behavior was changed during this step.  
