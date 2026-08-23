param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$agentsFile = Join-Path $ProjectRoot 'AGENTS.md'
$block = @'
<!-- gemini-and-chatgpt:begin -->
# Gemini + ChatGPT v2 automatic engineering gate
For every implementation, bug fix, refactor, feature, test, configuration/build, dependency, security, or architecture-related coding task, automatically apply `.agents/skills/gemini-and-chatgpt/SKILL.md`. Do not wait for the user to mention the skill.

Use the v2 lifecycle with minimum ceremony: `orchestrator.py start` -> plan only when required -> implement -> `orchestrator.py verify` -> push/create or update an OPEN GitHub Pull Request -> independent ChatGPT Web review bound to the exact full 40-character PR HEAD SHA. Never review an unverified candidate or a PR HEAD that differs from the verified candidate.

For STANDARD/COMPLEX tasks, keep `.ai/project-context.json` fresh using `project_context_scan.py` before Planner/Architect work. SIMPLE tasks bypass Planner/Architect/context scanning. Count only requested product/source scope; GitHub/review infrastructure does not make a one-file task non-SIMPLE.

After the verified candidate is pushed and an OPEN PR exists, use this exact review flow:
1. Run `python .agents/skills/gemini-and-chatgpt/scripts/review_round.py --root .` as ONE invocation. The script performs atomic preparation, transport, and verdict recording using a dedicated headed reviewer-Chromium instance: it opens chatgpt.com, injects the prompt via CDP direct DOM injection, verifies the presence of mandatory `=== GEMINI_CHATGPT_REVIEW_BEGIN ===`, `=== GEMINI_CHATGPT_REVIEW_END ===`, and the unique `TARGET_HEAD_SHA` in the composer before submission, clicks Send exactly once, and awaits the final verdict capture. Do not run helper scripts or manual transport steps separately.
2. Exit code 0 = verdict recorded; exit code 4 = `REVIEWER_LOGIN_REQUIRED`: sign in once in the reviewer Chrome window and rerun the command; other exit codes = `BLOCKED` transport failure recorded in `.ai/gemini-chatgpt-actions.log`. Do not loop retries without human authorization.
3. Manual-typing fallback (ONLY on persistent CDP transport failure): invoke ONE Antigravity `browser_subagent` task that opens `https://chatgpt.com/`, focuses the composer, and enters the verbatim prompt using native input. CRITICAL: Use `Shift+Enter` for line breaks; do not use the clipboard; verify both review markers are present in the same single-draft message before clicking Send once. A partial send or second-message continuation is `BLOCKED`.

Do not scan Chrome debug ports or launch a dedicated reviewer Chrome/profile yourself. A partial/early send, missing marker, incomplete response, or browser failure is `BLOCKED`; do not send the remainder as a second message and do not loop browser attempts.

After `REQUEST_CHANGES`, evaluate findings, fix valid blockers, create and verify a new candidate, push the new PR HEAD, then repeat the same prepare -> one Browser Subagent review -> finalize flow in a fresh ChatGPT conversation. `APPROVED_TO_MERGE` stops at `RELEASE_GATE`. Automatic merge remains OFF unless the user explicitly enables it.

Do not run `pr_context.py`, standalone reviewer verifiers, helper `--help`, repeated `git status`/`gh pr view`, or GitHub Web merely for reassurance. `review_round.py` performs deterministic `git` + `gh` identity reconciliation during both prepare and finalize. Private-repository browser 404s are not validation failures because PR identity comes from `gh`.

During workflow/self-validation, treat both Skill copies as immutable unless the user explicitly asked to modify the tool. Never request or store GitHub/OpenAI secrets in project files or prompts. `orchestrator.py` and `review_round.py` append actions and results to `.ai/gemini-chatgpt-actions.log` and `.ai/gemini-chatgpt-actions.jsonl`; report the log path on failure or completion.

If `git`, GitHub CLI `gh`, GitHub authentication, or `origin` is missing, stop before review and tell the user to rerun `gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat`.
<!-- gemini-and-chatgpt:end -->
'@

if (Test-Path -LiteralPath $agentsFile) {
    $content = Get-Content -LiteralPath $agentsFile -Raw
    $patterns = @(
        '(?s)<!-- gemini-and-chatgpt:begin -->.*?<!-- gemini-and-chatgpt:end -->',
        '(?s)<!-- ai-pr-review-loop:begin -->.*?<!-- ai-pr-review-loop:end -->'
    )
    $updated = $content
    foreach ($pattern in $patterns) {
        $updated = [regex]::Replace($updated, $pattern, '')
    }
    $updated = $updated.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
} else {
    $updated = $block + "`r`n"
}

Set-Content -LiteralPath $agentsFile -Value $updated -Encoding UTF8
Write-Host "[OK] Automatic workspace rule updated in AGENTS.md for gemini-and-chatgpt v2."
