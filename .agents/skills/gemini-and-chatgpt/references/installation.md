# Installation and activation

## Canonical Windows UX

Keep one complete `gemini-and-chatgpt` source folder directly under the project root:

```text
<project>\
├── gemini-and-chatgpt\
│   ├── INSTALL-ANTIGRAVITY.bat
│   ├── SKILL.md
│   ├── scripts\
│   ├── references\
│   ├── schemas\
│   └── agents\
└── ...
```

Run:

```text
gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat
```

The installer refreshes exactly one project-local installation:

```text
<project>\.agents\skills\gemini-and-chatgpt\
```

It also writes one managed `gemini-and-chatgpt` block into project-root `AGENTS.md`. After installation, reload/open the **project root** in Antigravity and give ordinary natural-language coding tasks. Do not require the user to type a slash command or `Use gemini-and-chatgpt skill`.

Do not install AWF globally or stack a second workflow framework on top of this system.

## Installer behavior

The BAT installer:

1. verifies that the complete v2 runtime, references, and schemas are present beside the installer;
2. refuses to run from the installed `.agents\skills\gemini-and-chatgpt` directory so it cannot delete its own source;
3. removes the previous project-local skill copy and performs a clean refresh, preventing stale runtime files;
4. copies `agents`, `references`, `schemas`, `scripts`, `SKILL.md`, and `README.md`;
5. migrates/removes the old `ai-pr-review-loop` project-local skill when present;
6. installs/updates the managed `AGENTS.md` activation block;
7. checks Git, GitHub CLI `gh`, GitHub authentication, and `origin` onboarding.

Yes/No prompts explicitly show `(default Y)` when Enter means Yes. Enter must select the displayed default.

## GitHub prerequisites

Before the independent review phase, all of these must be true:

```text
git status
git remote get-url origin
gh auth status
```

The candidate branch must be pushed and an **OPEN** GitHub Pull Request must exist. The exact full 40-character PR HEAD SHA must equal the candidate SHA that passed the Central Verification Gate.

If GitHub CLI, authentication, or `origin` is missing, rerun the installer. Never paste a PAT or other credential into Antigravity/ChatGPT prompts. Browser-based `gh auth login --web` is preferred; the installer also supports a secure PowerShell PAT prompt when needed.

## ChatGPT Web prerequisite

The normal reviewer path uses ChatGPT Web, not the OpenAI API. Use a fresh ChatGPT conversation for every review round. Antigravity should **not** open the ChatGPT tab itself; `review_round.py` reuses one reviewer target in an already-running debuggable Chrome and navigates it directly to a fresh ChatGPT conversation. It launches a dedicated persistent reviewer Chrome only as fallback. After the candidate is pushed and an OPEN PR exists, Antigravity runs only:

```text
python .agents/skills/gemini-and-chatgpt/scripts/review_round.py --root .
```

That command owns PR/HEAD reconciliation, immutable prompt generation, direct fill, zero-attachment/readback verification, Send, response wait, parsing, and lifecycle transition. It never uses Windows clipboard, `Ctrl+V`, simulated typing, `Shift+Enter`, or Enter transport.

If the already-open Antigravity Chrome does not expose a usable DevTools endpoint, a dedicated reviewer Chrome fallback may open. If it requests ChatGPT login, sign in once and rerun the same command. The fallback profile persists under `%LOCALAPPDATA%\GeminiChatGPTReviewer\ChromeProfile` and must never be copied into the repository.

## Release behavior

`APPROVED_TO_MERGE` stops at the human release gate. **Automatic merge is OFF by default.** A new PR HEAD invalidates approval for the previous HEAD.

## Updating

Update/replace the canonical `<project>\gemini-and-chatgpt` source folder, then run `INSTALL-ANTIGRAVITY.bat` again. The installer cleanly refreshes the installed project-local skill and managed activation block.


## ChatGPT reviewer browser

`review_round.py` owns the ChatGPT Web tab. It first reuses an already-running debuggable Chrome, preferring the Antigravity-owned process, and reuses one persisted reviewer tab rather than creating/clicking new tabs repeatedly. Only if no usable CDP endpoint exists does it launch/reuse `%LOCALAPPDATA%\GeminiChatGPTReviewer\ChromeProfile` as fallback. There is no simulated typing fallback. If fallback login is required, sign in once and rerun `review_round.py --root .`. Never copy browser profile/cookies into the repository.

For diagnostics, copy `.ai\gemini-chatgpt-actions.log`. It is written in-process by the workflow and includes compact phase/command/status/duration records without running extra logger commands.
