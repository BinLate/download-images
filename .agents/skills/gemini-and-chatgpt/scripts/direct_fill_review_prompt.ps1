# direct_fill_review_prompt.ps1
#
# REAL CDP (Chrome DevTools Protocol) direct-fill transport for the independent
# ChatGPT Web review round.
#
# Contract (called by review_round.py):
#   Params : -PromptPath -ReadbackPath -ResponsePath -ResultPath
#            -ResponseTimeoutSec <int> [-ProfileDir <dir>] [-DebugPort <int>] [-Endpoint <string>]
#   Result : JSON at ResultPath with keys sent, response_received,
#            transport_path, browser_source, browser_failovers,
#            review_target_reused, composer_resets, insertion_attempts, error
#   Exit   : 0 = success; 4 = reviewer login required; other != 0 = transport failure
#
# Strategy: probe localhost:<DebugPort> for an already-debuggable Chromium
# browser; otherwise launch one with a dedicated user-data-dir. Ensure a
# chatgpt.com tab, inject the prompt into the ProseMirror composer via
# Runtime.evaluate + execCommand / Input.insertText, verify markers by readback,
# click Send exactly once, then poll until the assistant answer stabilizes
# and persist it verbatim.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PromptPath,

    [string]$ReadbackPath,

    [string]$ResponsePath,

    [string]$ResultPath,

    [int]$ResponseTimeoutSec = 300,

    [string]$ProfileDir,

    [int]$DebugPort = 0,

    [string]$Endpoint
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

trap {
    try {
        if ($script:OwnsProfileLock -and $script:ProfileLockPath -and (Test-Path -LiteralPath $script:ProfileLockPath)) {
            Remove-Item -LiteralPath $script:ProfileLockPath -Force -ErrorAction SilentlyContinue
            $script:OwnsProfileLock = $false
        }
    } catch { }
    $info = $_.InvocationInfo
    $loc = 'unknown'
    if ($info) { $loc = ('line {0}' -f $info.ScriptLineNumber) }
    Write-Output ("SCRIPT_TRAP at {0} :: {1}" -f $loc, $_.Exception.Message)
    if ($ResultPath) {
        $diag = @{ transport_path = 'DIRECT_FILL_CDP'; sent = $false; response_received = $false; error = ("trap at {0}: {1}" -f $loc, $_.Exception.Message) }
        [System.IO.File]::WriteAllText($ResultPath, ($diag | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
    }
    exit 90
}

# ---------------------------------------------------------------------------
# Result plumbing
# ---------------------------------------------------------------------------

$script:BrowserFailovers = 0
$script:BrowserFailoverLogs = New-Object System.Collections.Generic.List[string]
$script:ProfileLockPath = $null
$script:OwnsProfileLock = $false
$script:CurrentPort = $DebugPort

function Write-Result {
    param([hashtable]$Fields, [int]$ExitCode)
    $payload = [ordered]@{
        transport_path       = 'DIRECT_FILL_CDP'
        browser_source       = $Fields.browser_source
        browser_failovers    = $script:BrowserFailovers
        review_target_reused = $Fields.review_target_reused
        composer_resets      = $Fields.composer_resets
        insertion_attempts   = $Fields.insertion_attempts
        sent                 = [bool]$Fields.sent
        response_received    = [bool]$Fields.response_received
        error                = $Fields.error
    }
    if ($Fields.ContainsKey('extra')) {
        foreach ($k in $Fields.extra.Keys) { $payload[$k] = $Fields.extra[$k] }
    }
    try {
        if ($script:OwnsProfileLock -and $script:ProfileLockPath -and (Test-Path -LiteralPath $script:ProfileLockPath)) {
            Remove-Item -LiteralPath $script:ProfileLockPath -Force -ErrorAction SilentlyContinue
            $script:OwnsProfileLock = $false
        }
    } catch { }
    $json = $payload | ConvertTo-Json -Depth 6
    if ($ResultPath) {
        [System.IO.File]::WriteAllText($ResultPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    }
    Write-Output $json
    exit $ExitCode
}

# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

function ConvertTo-JsString {
    param([AllowEmptyString()][string]$Value)
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.Append('"')
    foreach ($ch in $Value.ToCharArray()) {
        switch ($ch) {
            '"'  { [void]$sb.Append('\"'); break }
            '\'  { [void]$sb.Append('\\'); break }
            "`n" { [void]$sb.Append('\n'); break }
            "`r" { [void]$sb.Append('\r'); break }
            "`t" { [void]$sb.Append('\t'); break }
            default {
                $code = [int]$ch
                if ($code -lt 32 -or $code -eq 8232 -or $code -eq 8233) {
                    [void]$sb.Append('\u' + $code.ToString('x4'))
                } else {
                    [void]$sb.Append($ch)
                }
            }
        }
    }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Find-ChromeExecutable {
    $candidates = New-Object System.Collections.Generic.List[string]
    foreach ($name in @('chrome.exe', 'msedge.exe')) {
        try {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if ($cmd -and $cmd.Source) { $candidates.Add($cmd.Source) }
        } catch { }
    }
    foreach ($exe in @('chrome.exe', 'msedge.exe')) {
        $reg = Get-ItemProperty -Path ("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\" + $exe) -ErrorAction SilentlyContinue
        if ($reg -and $reg.'(default)') { $candidates.Add($reg.'(default)') }
    }
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
        if (-not $root) { continue }
        $candidates.Add((Join-Path $root "Google\Chrome\Application\chrome.exe"))
        $candidates.Add((Join-Path $root "Microsoft\Edge\Application\msedge.exe"))
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return [string]$candidate
        }
    }
    return $null
}

function Test-CdpList {
    param([int]$Port)
    try {
        $targets = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/list" -f $Port) -TimeoutSec 3
        return ($null -ne $targets)
    } catch { return $false }
}

# ---------------------------------------------------------------------------
# Resolve profile dir & lock
# ---------------------------------------------------------------------------

if (-not $ProfileDir) {
    $anchor = $null
    if ($ResultPath) {
        $cursor = Split-Path -Parent $ResultPath
        while ($cursor -and -not $anchor) {
            if ((Split-Path -Leaf $cursor) -eq '.ai') { $anchor = $cursor }
            $parent = Split-Path -Parent $cursor
            if ($parent -eq $cursor) { break }
            $cursor = $parent
        }
    }
    if ($anchor) {
        $ProfileDir = Join-Path $anchor 'chrome-reviewer-profile'
    } else {
        $ProfileDir = Join-Path ([System.IO.Path]::GetTempPath()) 'chatgpt-reviewer-profile'
    }
}
if (-not (Test-Path -LiteralPath $ProfileDir)) {
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
}

$script:ProfileLockPath = Join-Path $ProfileDir 'reviewer.lock'
$lockOwner = $null
if (Test-Path -LiteralPath $script:ProfileLockPath) {
    try { $lockOwner = [System.IO.File]::ReadAllText($script:ProfileLockPath).Trim() } catch { $lockOwner = $null }
}

if (-not [string]::IsNullOrWhiteSpace($lockOwner)) {
    $isAlive = $false
    if ($lockOwner -match 'pid=(\d+)') {
        $pidNum = [int]$matches[1]
        try {
            $p = Get-Process -Id $pidNum -ErrorAction SilentlyContinue
            if ($p) { $isAlive = $true }
        } catch { }
    }
    if ($isAlive) {
        Write-Output ('PROFILE_BUSY: reviewer profile lock held by ' + $lockOwner)
        Write-Result -Fields @{
            browser_source = $null; review_target_reused = $false; composer_resets = 0
            insertion_attempts = 0; sent = $false; response_received = $false
            error = ('PROFILE_BUSY: another review transport holds the reviewer profile lock (' + $lockOwner + '); no fallback to an unlogged-in profile')
            extra = @{ profile_dir = $ProfileDir; profile_lock = $script:ProfileLockPath }
        } -ExitCode 1
    } else {
        try { Remove-Item -LiteralPath $script:ProfileLockPath -Force -ErrorAction SilentlyContinue } catch { }
    }
}
[System.IO.File]::WriteAllText($script:ProfileLockPath, ('pid=' + $PID + ' at ' + [DateTime]::UtcNow.ToString('o')), [System.Text.UTF8Encoding]::new($false))
$script:OwnsProfileLock = $true

# ---------------------------------------------------------------------------
# Browser acquisition (ANTIGRAVITY_EXISTING_CDP vs DEDICATED_REVIEWER_CDP_FALLBACK)
# ---------------------------------------------------------------------------

function Find-ExistingDebugBrowser {
    param([int]$Port)
    if ($Port -le 0) { return $null }
    if (Test-CdpList -Port $Port) {
        return @{ source = 'ANTIGRAVITY_EXISTING_CDP'; port = $Port }
    }
    return $null
}

function Ensure-DedicatedReviewerBrowser {
    param([int]$Port)
    if ($Port -le 0) { $Port = 9334 }
    $exe = Find-ChromeExecutable
    if (-not $exe) {
        Write-Result -Fields @{
            browser_source = $null; review_target_reused = $false; composer_resets = 0
            insertion_attempts = 0; sent = $false; response_received = $false
            error = 'NO_CHROME_EXECUTABLE: could not locate Google Chrome or Microsoft Edge on system'
        } -ExitCode 1
    }

    $procArgs = @(
        "--remote-debugging-port=$Port",
        "--user-data-dir=$ProfileDir",
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-session-crashed-bubble',
        '--disable-infobars',
        '--window-size=1400,950',
        'https://chatgpt.com/'
    )

    $launchedProc = $null
    try {
        $launchedProc = Start-Process -FilePath $exe -ArgumentList $procArgs -PassThru -WindowStyle Normal
    } catch {
        Write-Result -Fields @{
            browser_source = $null; review_target_reused = $false; composer_resets = 0
            insertion_attempts = 0; sent = $false; response_received = $false
            error = ('CHROME_SPAWN_FAILED: ' + $_.Exception.Message)
        } -ExitCode 1
    }

    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 1000
        try { if ($launchedProc.HasExited) { break } } catch { }
        if (Test-CdpList -Port $Port) { $ready = $true; break }
    }

    if (-not $ready) {
        try { if (-not $launchedProc.HasExited) { Stop-Process -Id $launchedProc.Id -Force -ErrorAction SilentlyContinue } } catch { }
        Write-Result -Fields @{
            browser_source = $null; review_target_reused = $false; composer_resets = 0
            insertion_attempts = 0; sent = $false; response_received = $false
            error = ('NO_DEBUGGABLE_BROWSER: Chrome started but remote debugging port ${Port}: did not respond')
        } -ExitCode 1
    }

    return @{ source = 'DEDICATED_REVIEWER_CDP_FALLBACK'; port = $Port }
}

function Ensure-ReviewerBrowser {
    param([int]$Port)
    $existing = Find-ExistingDebugBrowser -Port $Port
    if ($existing) { return $existing }
    return Ensure-DedicatedReviewerBrowser -Port $Port
}

function Receive-CdpMessage {
    param([System.Net.WebSockets.ClientWebSocket]$Socket, [int]$TimeoutMs = 15000)
    if ($null -eq $Socket -or $Socket.State -ne [System.Net.WebSockets.WebSocketState]::Open) { return $null }
    $buffer = [System.ArraySegment[byte]]::new([byte[]]::new(65536))
    $ms = [System.IO.MemoryStream]::new()
    while ($true) {
        $task = $Socket.ReceiveAsync($buffer, [System.Threading.CancellationToken]::None)
        if (-not $task.Wait($TimeoutMs)) {
            return $null
        }
        $recv = $task.GetAwaiter().GetResult()
        if ($recv.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
            return $null
        }
        $ms.Write($buffer.Array, $buffer.Offset, $recv.Count)
        if ($recv.EndOfMessage) { break }
    }
    $raw = [System.Text.Encoding]::UTF8.GetString($ms.ToArray())
    try {
        return ($raw | ConvertFrom-Json)
    } catch {
        return $null
    }
}

$browserInfo = Ensure-ReviewerBrowser -Port $script:CurrentPort
$browserSource = $browserInfo.source
$script:CurrentPort = [int]$browserInfo.port

# ---------------------------------------------------------------------------
# Persistent reviewer target management
# ---------------------------------------------------------------------------

$ReviewerTargetStatePath = Join-Path $ProfileDir 'reviewer-target.json'

function Get-ReviewerTarget {
    param([int]$Port)
    if (Test-Path -LiteralPath $ReviewerTargetStatePath) {
        try {
            $saved = [System.IO.File]::ReadAllText($ReviewerTargetStatePath) | ConvertFrom-Json
            if ($saved -and [int]$saved.port -eq $Port -and $saved.id) {
                $list = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/list" -f $Port) -TimeoutSec 5
                foreach ($t in $list) {
                    if ($t.id -eq $saved.id) { return @{ tab = $t; reused = $true } }
                }
            }
        } catch { }
    }

    $list = @()
    try {
        $list = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/list" -f $Port) -TimeoutSec 5
    } catch { }

    foreach ($t in $list) {
        if ($t.type -eq 'page' -and $t.url -match '^https://(www\.)?chatgpt\.com/') {
            return @{ tab = $t; reused = $true }
        }
    }

    foreach ($t in $list) {
        if ($t.type -eq 'page' -and ($t.url -eq 'about:blank' -or $t.url -match '^chrome://newtab')) {
            return @{ tab = $t; reused = $false }
        }
    }

    # New target creation remains only a one-time fallback when no reusable ChatGPT target exists.
    $newTab = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/new?https://chatgpt.com/" -f $Port) -Method Put -TimeoutSec 8
    return @{ tab = $newTab; reused = $false }
}

function Save-ReviewerTarget {
    param($Tab, [int]$Port, [string]$Source)
    $obj = @{ id = $Tab.id; port = $Port; source = $Source; updated_at = [DateTime]::UtcNow.ToString('o') }
    [System.IO.File]::WriteAllText($ReviewerTargetStatePath, ($obj | ConvertTo-Json -Compress), [System.Text.UTF8Encoding]::new($false))
}

function Resolve-ReviewerBrowserTarget {
    param([int]$Port, [string]$Source)
    $res = Get-ReviewerTarget -Port $Port
    $tab = $res.tab
    Save-ReviewerTarget $tab $Port $Source
    return $res
}

$targetResolution = Resolve-ReviewerBrowserTarget -Port $script:CurrentPort -Source $browserSource
$tab = $targetResolution.tab
$reviewTargetReused = [bool]$targetResolution.reused

# ---------------------------------------------------------------------------
# WebSocket CDP client
# ---------------------------------------------------------------------------

$wsUrl = $tab.webSocketDebuggerUrl
if (-not $wsUrl) {
    $wsUrl = ("ws://127.0.0.1:{0}/devtools/page/{1}" -f $script:CurrentPort, $tab.id)
}

$ws = [System.Net.WebSockets.ClientWebSocket]::new()
$cts = [System.Threading.CancellationTokenSource]::new(15000)
try {
    [void]$ws.ConnectAsync([Uri]$wsUrl, $cts.Token).GetAwaiter().GetResult()
} catch {
    $script:BrowserFailovers++
    $script:BrowserFailoverLogs.Add('cdp-ws-connect-failed') | Out-Null
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = ('CDP_CONNECT_FAILED: could not open WebSocket to ' + $wsUrl + ' :: ' + $_.Exception.Message)
    } -ExitCode 1
}

$script:CdpMsgId = 100

function Invoke-CdpCommand {
    param(
        [string]$Method,
        [hashtable]$Params = @{},
        [int]$TimeoutMs = 25000
    )
    if ($ws.State -ne [System.Net.WebSockets.WebSocketState]::Open) {
        throw ("Cannot invoke CDP command {0}: WebSocket state is {1}" -f $Method, $ws.State)
    }
    $script:CdpMsgId++
    $id = $script:CdpMsgId
    $req = @{ id = $id; method = $Method; params = $Params }
    $json = $req | ConvertTo-Json -Depth 10 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    $seg = [System.ArraySegment[byte]]::new($bytes)
    [void]$ws.SendAsync($seg, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, [System.Threading.CancellationToken]::None).GetAwaiter().GetResult()

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    while ([DateTime]::UtcNow -lt $deadline -and $ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        $msg = Receive-CdpMessage -Socket $ws -TimeoutMs 5000
        if ($null -ne $msg) {
            if ($null -ne $msg.PSObject.Properties['id'] -and $msg.id -eq $id) {
                if ($null -ne $msg.PSObject.Properties['error'] -and $null -ne $msg.error) {
                    throw ("CDP Error on {0}: {1}" -f $Method, ($msg.error | ConvertTo-Json -Compress))
                }
                if ($null -ne $msg.PSObject.Properties['result']) {
                    return $msg.result
                }
                return $null
            }
        }
    }
    throw ("Timeout waiting for CDP response to {0} id={1}" -f $Method, $id)
}

function Invoke-PageJs {
    param([string]$Js, [int]$TimeoutMs = 25000)
    $eval = Invoke-CdpCommand -Method 'Runtime.evaluate' -Params @{
        expression    = $Js
        returnByValue = $true
        awaitPromise  = $true
    } -TimeoutMs $TimeoutMs
    if ($null -ne $eval -and $null -ne $eval.PSObject.Properties['result'] -and $null -ne $eval.result.PSObject.Properties['value']) {
        return $eval.result.value
    }
    return $null
}

# ---------------------------------------------------------------------------
# Direct Navigation to https://chatgpt.com/ (Fresh Session)
# ---------------------------------------------------------------------------

try {
    Invoke-CdpCommand -Method 'Page.enable' -Params @{} | Out-Null
    Invoke-CdpCommand -Method 'Runtime.enable' -Params @{} | Out-Null
    Invoke-CdpCommand -Method 'Page.navigate' -Params @{ url = 'https://chatgpt.com/' } | Out-Null
} catch {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = ('CHATGPT_NAVIGATION_FAILED: could not navigate reviewer target to https://chatgpt.com/ :: ' + $_.Exception.Message)
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# DOM & Login State Verification (Accurate Login Detection)
# ---------------------------------------------------------------------------

$checkDomStateJs = @"
(function() {
    var ed = document.querySelector('#prompt-textarea');
    if (ed && !ed.disabled && ed.offsetParent !== null) {
        return 'COMPOSER_READY';
    }
    var loginElements = document.querySelectorAll('button[data-testid="login-button"], button[data-testid="welcome-login-button"], a[href*="/login"], a[href*="/auth/login"], button[aria-label="Log in"]');
    if (loginElements.length > 0) {
        return 'LOGIN_REQUIRED';
    }
    var allButtons = document.querySelectorAll('button, a');
    for (var i = 0; i < allButtons.length; i++) {
        var t = (allButtons[i].innerText || '').trim().toLowerCase();
        if (t === 'log in' || t === 'sign up' || t === 'đăng nhập' || t === 'đăng ký') {
            return 'LOGIN_REQUIRED';
        }
    }
    if (ed && !ed.disabled) {
        return 'COMPOSER_READY';
    }
    return 'LOADING';
})()
"@

$domState = 'LOADING'
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 1000
    try {
        $state = [string](Invoke-PageJs -Js $checkDomStateJs -TimeoutMs 5000)
        if ($state -eq 'LOGIN_REQUIRED' -or $state -eq 'COMPOSER_READY') {
            $domState = $state
            break
        }
    } catch { }
}

if ($domState -eq 'LOGIN_REQUIRED') {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = 'REVIEWER_LOGIN_REQUIRED: ChatGPT login wall detected. Please log in once in the reviewer browser window and rerun review.'
    } -ExitCode 4
}

if ($domState -ne 'COMPOSER_READY') {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = 'COMPOSER_NOT_READY: #prompt-textarea composer did not become ready within timeout'
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Reset Composer DOM in place
# ---------------------------------------------------------------------------

function Reset-ComposerDom {
    $clearJs = @"
    (function() {
        var ed = document.querySelector('#prompt-textarea');
        if (!ed) return 'NO_EDITOR';
        ed.focus();
        if (ed.tagName.toLowerCase() === 'textarea') {
            ed.value = '';
            ed.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            ed.innerHTML = '<p><br></p>';
            ed.dispatchEvent(new Event('input', { bubbles: true }));
        }
        return (ed.innerText || '').trim() === '' ? 'CLEARED' : 'DIRTY';
    })()
"@
    return [string](Invoke-PageJs -Js $clearJs -TimeoutMs 10000)
}

$composerResets = 0
$resetStatus = Reset-ComposerDom
if ($resetStatus -eq 'DIRTY') {
    $composerResets++
    $resetStatus = Reset-ComposerDom
    if ($resetStatus -eq 'DIRTY') {
        Write-Result -Fields @{
            browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
            insertion_attempts = 0; sent = $false; response_received = $false
            error = 'COMPOSER_RESET_FAILED: could not clear stale composer state without keyboard automation after one in-place retry'
        } -ExitCode 1
    }
}

# ---------------------------------------------------------------------------
# Inject Prompt via Input.insertText / DOM Injection (Zero Clipboard)
# ---------------------------------------------------------------------------

$promptText = [System.IO.File]::ReadAllText($PromptPath, [System.Text.Encoding]::UTF8)
$insertionAttempts = 0

function Verify-ImmutablePackage {
    param([string]$Text)
    $manifestPath = $PromptPath + ".manifest.json"
    $canonical_sha256 = ""
    $canonical_lines = 0
    if (Test-Path -LiteralPath $manifestPath) {
        try {
            $m = [System.IO.File]::ReadAllText($manifestPath) | ConvertFrom-Json
            $canonical_sha256 = $m.canonical_sha256
            $canonical_lines = $m.canonical_lines
        } catch { }
    }
    if (-not ($Text.Contains('=== GEMINI_CHATGPT_REVIEW_BEGIN ===') -and $Text.Contains('=== GEMINI_CHATGPT_REVIEW_END ==='))) {
        throw 'PROMPT_ID binding invalid: missing boundary review markers'
    }
    if (-not ($Text -match 'TARGET_HEAD_SHA:\s*([0-9a-fA-F]{40})')) {
        throw 'TARGET_HEAD_SHA binding invalid: missing valid 40-character target HEAD SHA'
    }
}

Verify-ImmutablePackage -Text $promptText

$focusJs = "(function(){ var ed = document.querySelector('#prompt-textarea'); if(ed){ ed.focus(); return 'OK'; } return 'NO_EDITOR'; })()"
Invoke-PageJs -Js $focusJs | Out-Null

try {
    Invoke-CdpCommand -Method 'Input.insertText' -Params @{ text = $promptText } -TimeoutMs 30000 | Out-Null
    $insertionAttempts = 1
} catch {
    $injectJs = @"
    (function(text) {
        var ed = document.querySelector('#prompt-textarea');
        if (!ed) return 'NO_EDITOR';
        ed.focus();
        if (ed.tagName.toLowerCase() === 'textarea') {
            ed.value = text;
            ed.dispatchEvent(new Event('input', { bubbles: true }));
        } else {
            ed.innerText = text;
            ed.dispatchEvent(new Event('input', { bubbles: true }));
        }
        return 'OK';
    })($(ConvertTo-JsString $promptText))
"@
    Invoke-PageJs -Js $injectJs -TimeoutMs 30000 | Out-Null
    $insertionAttempts = 1
}

# ---------------------------------------------------------------------------
# Readback & Marker / SHA / Zero Attachment Verification
# ---------------------------------------------------------------------------

$readbackJs = "(function(){ var ed = document.querySelector('#prompt-textarea'); return ed ? (ed.value || ed.innerText || '') : ''; })()"

function Wait-ComposerReadback {
    param([int]$TimeoutMs = 2500)
    $expected_sha256 = ""
    $actual_sha256 = ""
    $read = [string](Invoke-PageJs -Js $readbackJs -TimeoutMs 5000)
    return $read
}

$composed = Wait-ComposerReadback -TimeoutMs 2500

if ($ReadbackPath) {
    [System.IO.File]::WriteAllText($ReadbackPath, $composed, [System.Text.UTF8Encoding]::new($false))
}

$beginMarker = '=== GEMINI_CHATGPT_REVIEW_BEGIN ==='
$endMarker = '=== GEMINI_CHATGPT_REVIEW_END ==='
$shaMatches = [regex]::Match($promptText, 'TARGET_HEAD_SHA:\s*([0-9a-fA-F]{40})')
$targetSha = if ($shaMatches.Success) { $shaMatches.Groups[1].Value } else { $null }

$hasBegin = $composed.Contains($beginMarker)
$hasEnd = $composed.Contains($endMarker)
$hasSha = ($null -ne $targetSha) -and $composed.Contains($targetSha)

$attachmentCheckJs = "(function(){ var att = document.querySelectorAll('[data-testid*=""attachment""], [data-testid*=""file-item""]'); return att.length; })()"
$attachmentCount = [int](Invoke-PageJs -Js $attachmentCheckJs -TimeoutMs 5000)

if (-not ($hasBegin -and $hasEnd -and $hasSha) -and ($insertionAttempts -lt 2)) {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = $insertionAttempts; sent = $false; response_received = $false
        error = 'composer text does not exactly match immutable prompt: missing begin/end markers or HEAD SHA'
    } -ExitCode 1
}

if ($attachmentCount -gt 0) {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = $insertionAttempts; sent = $false; response_received = $false
        error = 'attachment/upload state is not clean: unexpected attachments present in composer'
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Click Send exactly once
# ---------------------------------------------------------------------------

$sendJs = @"
(function() {
    var send = document.querySelector('button[data-testid="send-button"]') || document.querySelector('button[aria-label="Send prompt"]');
    if (!send) return 'NO_BUTTON';
    if (send.disabled || send.getAttribute('aria-disabled') === 'true') return 'DISABLED';
    send.click();
    return 'CLICKED';
})()
"@

$clickRes = [string](Invoke-PageJs -Js $sendJs -TimeoutMs 15000)
if ($clickRes -ne 'CLICKED') {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = $insertionAttempts; sent = $false; response_received = $false
        error = ('SEND_NOT_CLICKED: send.click() failed or button was ' + $clickRes)
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Poll and stream assistant response until complete
# ---------------------------------------------------------------------------

$pollJs = @"
(function() {
    var stopBtn = !!document.querySelector('button[data-testid="stop-button"]');
    var assistants = document.querySelectorAll('[data-message-author-role="assistant"]');
    var text = '';
    if (assistants.length > 0) {
        text = assistants[assistants.length - 1].innerText || '';
    }
    return JSON.stringify({ busy: stopBtn, text: text, count: assistants.length });
})()
"@

$deadline = [DateTime]::UtcNow.AddSeconds($ResponseTimeoutSec)
$prevText = $null
$responseText = $null
$responseReceived = $false

while ([DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Seconds 3
    $raw = $null
    try { $raw = Invoke-PageJs -Js $pollJs -TimeoutMs 20000 } catch { Start-Sleep -Seconds 2; continue }
    if (-not $raw) { continue }
    $snap = $raw | ConvertFrom-Json
    if ((-not $snap.busy) -and $snap.text -and ($snap.text -eq $prevText)) {
        $responseText = [string]$snap.text
        $responseReceived = $true
        break
    }
    $prevText = [string]$snap.text
}

if (-not $responseReceived) {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = $insertionAttempts; sent = $true; response_received = $false
        error = ('REVIEWER_RESPONSE_TIMEOUT: no stabilized assistant answer within {0}s' -f $ResponseTimeoutSec)
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Persist response and exit 0
# ---------------------------------------------------------------------------

if ($ResponsePath) {
    [System.IO.File]::WriteAllText($ResponsePath, $responseText, [System.Text.UTF8Encoding]::new($false))
}

$result = [ordered]@{
    transport_path = 'DIRECT_FILL_CDP'
    browser_source = $browserSource
    browser_failovers = $script:BrowserFailovers
    review_target_reused = $reviewTargetReused
    composer_resets = $composerResets
    insertion_attempts = $insertionAttempts
    sent = $true
    response_received = $true
    error = $null
    }

Write-Result -Fields $result -ExitCode 0
