@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ================================================
echo  Gemini + ChatGPT v2 Software Team - Installer
echo ================================================
echo.

set "TOOL_DIR=%~dp0"
if "%TOOL_DIR:~-1%"=="\" set "TOOL_DIR=%TOOL_DIR:~0,-1%"
for %%I in ("%TOOL_DIR%\..") do set "PROJECT_ROOT=%%~fI"
for %%I in ("%PROJECT_ROOT%") do set "DEFAULT_REPO=%%~nxI"
set "SKILL_DEST=%PROJECT_ROOT%\.agents\skills\gemini-and-chatgpt"
set "OLD_SKILL_DEST=%PROJECT_ROOT%\.agents\skills\ai-pr-review-loop"

echo Project detected:
echo   %PROJECT_ROOT%
echo.
echo Skill will be installed to:
echo   %SKILL_DEST%
echo.

if /I "%TOOL_DIR%"=="%SKILL_DEST%" (
  echo [ERROR] Do not run this installer from the installed skill directory.
  echo Run the canonical project copy instead:
  echo   ^<project^>\gemini-and-chatgpt\INSTALL-ANTIGRAVITY.bat
  pause
  exit /b 1
)

for %%F in (SKILL.md README.md scripts\orchestrator.py scripts\action_log.py scripts\architect_store.py scripts\context_store.py scripts\project_context_scan.py scripts\state_machine.py scripts\task_classifier.py scripts\plan_store.py scripts\verification_gate.py scripts\review_prompt.py scripts\review_package_guard.py scripts\direct_fill_review_prompt.ps1 scripts\review_round.py scripts\verify_review_transport.py scripts\verify_review_attachments.py scripts\verify_review_target.py scripts\review_runtime_log.py scripts\parse_review.py scripts\pr_context.py scripts\workflow_state.py scripts\install_agents_rule.ps1 references\workflow.md references\architect-contract.md references\builder-contract.md references\review-contract.md references\installation.md schemas\task-state.schema.json schemas\plan.schema.json schemas\verification-evidence.schema.json schemas\project-context.schema.json schemas\checkpoint.schema.json) do (
  if not exist "%TOOL_DIR%\%%F" (
    echo [ERROR] Required v2 file is missing: %%F
    echo Keep the complete gemini-and-chatgpt folder together before installing.
    pause
    exit /b 1
  )
)

if not exist "%PROJECT_ROOT%\.agents" mkdir "%PROJECT_ROOT%\.agents" >nul 2>&1
if not exist "%PROJECT_ROOT%\.agents\skills" mkdir "%PROJECT_ROOT%\.agents\skills" >nul 2>&1
if exist "%SKILL_DEST%" (
  echo [INFO] Refreshing existing project-local skill installation...
  rmdir /S /Q "%SKILL_DEST%" >nul 2>&1
)
if not exist "%SKILL_DEST%" mkdir "%SKILL_DEST%" >nul 2>&1
if not exist "%SKILL_DEST%" (
  echo [ERROR] Windows could not create:
  echo   %SKILL_DEST%
  pause
  exit /b 1
)

copy /Y "%TOOL_DIR%\SKILL.md" "%SKILL_DEST%\SKILL.md" >nul
if errorlevel 1 goto :copy_error
if exist "%TOOL_DIR%\README.md" copy /Y "%TOOL_DIR%\README.md" "%SKILL_DEST%\README.md" >nul
for %%D in (agents references schemas scripts) do (
  if exist "%TOOL_DIR%\%%D" (
    if not exist "%SKILL_DEST%\%%D" mkdir "%SKILL_DEST%\%%D" >nul 2>&1
    xcopy "%TOOL_DIR%\%%D\*" "%SKILL_DEST%\%%D\" /E /I /Y /Q >nul
    if errorlevel 1 goto :copy_error
  )
)
echo [OK] Antigravity v2 skill refreshed as gemini-and-chatgpt.

rem Migrate from the old skill name used by earlier versions.
if exist "%OLD_SKILL_DEST%" (
  echo [INFO] Removing old skill folder: %OLD_SKILL_DEST%
  rmdir /S /Q "%OLD_SKILL_DEST%" >nul 2>&1
  if exist "%OLD_SKILL_DEST%" (
    echo [WARN] Could not remove the old ai-pr-review-loop folder.
    echo        Close Antigravity and delete it manually to avoid duplicate skills.
  ) else (
    echo [OK] Old ai-pr-review-loop installation removed.
  )
)

if exist "%TOOL_DIR%\scripts\install_agents_rule.ps1" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%TOOL_DIR%\scripts\install_agents_rule.ps1" -ProjectRoot "%PROJECT_ROOT%"
  if errorlevel 1 echo [WARN] Could not update AGENTS.md automatically.
) else (
  echo [WARN] install_agents_rule.ps1 is missing; automatic activation rule was not updated.
)

echo.
echo ---------------- Git / GitHub setup ----------------
where git >nul 2>&1
if errorlevel 1 (
  echo [WARN] Git is not installed or not in PATH.
  echo        Install Git for Windows, then run this installer again.
  goto :finish
)
echo [OK] Git found.

git -C "%PROJECT_ROOT%" rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo.
  set "INITGIT="
  set /p "INITGIT=This project is not a Git repository. Initialize Git now? [Y/n] (default Y): "
  if "!INITGIT!"=="" set "INITGIT=Y"
  if /I "!INITGIT!"=="Y" (
    git -C "%PROJECT_ROOT%" init
    if errorlevel 1 (
      echo [ERROR] Could not initialize Git in this project.
      goto :finish
    )
    echo [OK] Git repository initialized.
  ) else (
    echo [WARN] Git initialization skipped. PR review cannot run until Git is configured.
    goto :finish
  )
) else (
  echo [OK] Project is already a Git repository.
)

where gh >nul 2>&1
if errorlevel 1 (
  echo.
  echo [WARN] GitHub CLI ^(gh^) is not installed or not in PATH.
  where winget >nul 2>&1
  if not errorlevel 1 (
    set "INSTALLGH="
    set /p "INSTALLGH=Install GitHub CLI now with winget? [Y/n] (default Y): "
    if "!INSTALLGH!"=="" set "INSTALLGH=Y"
    if /I "!INSTALLGH!"=="Y" (
      winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
      echo.
      echo If gh is still not found in this window, close it and run this installer again.
    )
  )
  goto :finish
)
echo [OK] GitHub CLI found.

gh auth status >nul 2>&1
if errorlevel 1 (
  echo.
  echo GitHub is NOT connected yet.
  echo Choose a login method:
  echo   1. Browser login ^(recommended^)
  echo   2. Personal Access Token ^(PAT^)
  echo   3. Skip for now
  set /p GHMODE=Enter 1, 2, or 3: 

  if "!GHMODE!"=="1" (
    echo.
    echo Starting GitHub browser login...
    gh auth login --hostname github.com --git-protocol https --web
  ) else if "!GHMODE!"=="2" (
    echo.
    echo Paste your GitHub token in the secure PowerShell prompt.
    echo For classic PAT, repo scope is usually required for private repos.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$s=Read-Host 'GitHub PAT' -AsSecureString; $b=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s); try {$t=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b); $t | gh auth login --hostname github.com --git-protocol https --with-token} finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)}"
  ) else (
    echo [WARN] GitHub login skipped.
    goto :finish
  )
)

gh auth status >nul 2>&1
if errorlevel 1 (
  echo [ERROR] GitHub authentication is still not configured.
  goto :finish
)
echo [OK] GitHub account connected.

git -C "%PROJECT_ROOT%" remote get-url origin >nul 2>&1
if not errorlevel 1 (
  for /f "delims=" %%R in ('git -C "%PROJECT_ROOT%" remote get-url origin') do set "ORIGIN_URL=%%R"
  echo [OK] GitHub remote already configured:
  echo      !ORIGIN_URL!
  goto :github_ready
)

echo.
echo This project is not connected to a GitHub repository yet.
echo Choose one:
echo   1. Create a NEW GitHub repository and connect it ^(recommended^)
echo   2. Connect to an EXISTING GitHub repository URL
echo   3. Skip for now
set /p REPO_MODE=Enter 1, 2, or 3: 

if "!REPO_MODE!"=="1" (
  set "REPO_NAME="
  set /p REPO_NAME=GitHub repository name [!DEFAULT_REPO!]: 
  if "!REPO_NAME!"=="" set "REPO_NAME=!DEFAULT_REPO!"
  echo Visibility:
  echo   1. Private ^(recommended^)
  echo   2. Public
  set /p VISMODE=Enter 1 or 2 [1]: 
  if "!VISMODE!"=="2" (set "VISIBILITY=public") else (set "VISIBILITY=private")
  gh repo create "!REPO_NAME!" --!VISIBILITY!
  if errorlevel 1 (
    echo [ERROR] Could not create the GitHub repository.
    goto :finish
  )
  for /f "delims=" %%U in ('gh api user -q .login') do set "GH_OWNER=%%U"
  if "!GH_OWNER!"=="" (
    echo [ERROR] Could not determine the connected GitHub account.
    goto :finish
  )
  set "NEW_REMOTE=https://github.com/!GH_OWNER!/!REPO_NAME!.git"
  git -C "%PROJECT_ROOT%" remote add origin "!NEW_REMOTE!"
  if errorlevel 1 (
    echo [ERROR] GitHub repo was created, but origin could not be added.
    echo         Add this remote manually: !NEW_REMOTE!
    goto :finish
  )
  echo [OK] New GitHub repository created and connected as origin.
  echo      !NEW_REMOTE!
) else if "!REPO_MODE!"=="2" (
  set "REPO_URL="
  set /p REPO_URL=Paste existing GitHub repository URL: 
  if "!REPO_URL!"=="" (
    echo [ERROR] Repository URL cannot be empty.
    goto :finish
  )
  git -C "%PROJECT_ROOT%" remote add origin "!REPO_URL!"
  if errorlevel 1 (
    echo [ERROR] Could not add origin remote.
    goto :finish
  )
  echo [OK] Existing GitHub repository connected as origin.
) else (
  echo [WARN] GitHub repository connection skipped.
  goto :finish
)

:github_ready
echo.
echo GitHub connection check:
git -C "%PROJECT_ROOT%" remote -v
echo.
echo [OK] GitHub setup is ready for commit, push, and Pull Request creation.
echo     The skill will push a task branch and create/update the PR BEFORE ChatGPT review.

goto :finish

:copy_error
echo [ERROR] Could not copy skill files.
echo Source:
echo   %TOOL_DIR%
echo Destination:
echo   %SKILL_DEST%
pause
exit /b 1

:finish
echo.
echo ================================================
echo  DONE
echo ================================================
echo.
echo Automatic mode is enabled through AGENTS.md.
echo You do NOT need to type "Use gemini-and-chatgpt skill".
echo.
echo Normal use:
echo   1. Open/reload the project root in Antigravity.
echo   2. Give your coding task normally.
echo   3. Antigravity must verify code, push a branch to GitHub, create/update a PR,
echo      then use one Antigravity Browser Subagent task to send the immutable review package, collect the response, and finalize the exact-SHA verdict.
echo.
echo Important:
echo   - If GitHub login/origin was skipped, run this installer again before review.
echo   - If Antigravity was already open, reload/reopen the workspace once.
echo   - Review browser interaction is handled end-to-end by one Antigravity Browser Subagent task. The legacy PowerShell/CDP transport is not used.
echo   - Diagnostics log: .ai\gemini-chatgpt-actions.log
echo   - Automatic merge is OFF by default.
echo.
pause
endlocal
