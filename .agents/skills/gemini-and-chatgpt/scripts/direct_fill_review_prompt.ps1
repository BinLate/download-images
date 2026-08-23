# direct_fill_review_prompt.ps1
#
# REAL CDP (Chrome DevTools Protocol) direct-fill transport for the independent
# ChatGPT Web review round.
#
# Contract (called by review_round.py):
#   Params : -PromptPath -ReadbackPath -ResponsePath -ResultPath
#            -ResponseTimeoutSec <int> [-ProfileDir <dir>] [-DebugPort <int>]
#   Result : JSON at ResultPath with keys sent, response_received,
#            transport_path, browser_source, browser_failovers,
#            review_target_reused, composer_resets, insertion_attempts, error
#   Exit   : 0 = success; 4 = reviewer login required; other != 0 = transport failure
#
# Strategy: probe localhost:<DebugPort> for an already-debuggable Chromium
# browser; otherwise launch one with a dedicated user-data-dir. Ensure a
# chatgpt.com tab, inject the prompt into the ProseMirror composer via
# Runtime.evaluate + execCommand (per-line, never bare Enter), verify markers
# by readback, click Send exactly once, then poll until the assistant answer
# stabilizes and persist it verbatim.

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PromptPath,

    [string]$ReadbackPath,

    [string]$ResponsePath,

    [string]$ResultPath,

    [int]$ResponseTimeoutSec = 300,

    [string]$ProfileDir,

    [int]$DebugPort = 9222
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

$script:BrowserFailovers = New-Object System.Collections.Generic.List[string]
$script:ProfileLockPath = $null
$script:OwnsProfileLock = $false

function Write-Result {
    param([hashtable]$Fields, [int]$ExitCode)
    $payload = [ordered]@{
        transport_path       = 'DIRECT_FILL_CDP'
        browser_source       = $Fields.browser_source
        browser_failovers    = $script:BrowserFailovers.ToArray()
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

function Get-ChromiumCandidatePaths {
    $list = New-Object System.Collections.Generic.List[string]
    foreach ($name in @('chrome.exe', 'msedge.exe')) {
        try {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if ($cmd -and $cmd.Source) { $list.Add($cmd.Source) }
        } catch { }
    }
    foreach ($exe in @('chrome.exe', 'msedge.exe')) {
        $reg = Get-ItemProperty -Path ("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\" + $exe) -ErrorAction SilentlyContinue
        if ($reg -and $reg.'(default)') { $list.Add($reg.'(default)') }
    }
    foreach ($root in @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA)) {
        if (-not $root) { continue }
        $list.Add((Join-Path $root "Google\Chrome\Application\chrome.exe"))
        $list.Add((Join-Path $root "Microsoft\Edge\Application\msedge.exe"))
    }
    return @($list | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique)
}

function Test-DebugEndpoint {
    try {
        $v = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/version" -f $DebugPort) -TimeoutSec 2
        return ($null -ne $v -and $null -ne $v.Browser)
    } catch { return $false }
}

# ---------------------------------------------------------------------------
# Resolve profile dir (default: <repo>/.ai/chrome-reviewer-profile derived
# from ResultPath ancestors, falling back to TEMP).
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
    if ($anchor) { $ProfileDir = Join-Path $anchor 'chrome-reviewer-profile' }
    else { $ProfileDir = Join-Path $env:TEMP 'chatgpt-reviewer-profile' }
}

# ---------------------------------------------------------------------------
# Single-flight profile lock: two Chromium processes cannot share one
# user-data-dir. A second launch silently joins the FIRST process WITHOUT the
# debug port -> the transport then talks to the wrong browser or hits the
# login wall. If the lock is held, fail fast with PROFILE_BUSY instead of
# degrading to a fresh (never logged-in) profile.
# ---------------------------------------------------------------------------

$script:ProfileLockPath = Join-Path $env:TEMP ('chatgpt-reviewer-profile.lock.port' + $DebugPort)
$lockOwner = $null
try {
    if (Test-Path -LiteralPath $script:ProfileLockPath) {
        $lockOwner = ([System.IO.File]::ReadAllText($script:ProfileLockPath)).Trim()
    }
} catch { $lockOwner = $null }

if (-not [string]::IsNullOrWhiteSpace($lockOwner)) {
    Write-Output ('PROFILE_BUSY: reviewer profile lock held by ' + $lockOwner)
    Write-Result -Fields @{
        browser_source = $null; review_target_reused = $false; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = ('PROFILE_BUSY: another review transport holds the reviewer profile lock (' + $lockOwner + '); no fallback to an unlogged-in profile')
        extra = @{ profile_dir = $ProfileDir; profile_lock = $script:ProfileLockPath }
    } -ExitCode 1
}
[System.IO.File]::WriteAllText($script:ProfileLockPath, ('pid=' + $PID + ' at ' + [DateTime]::UtcNow.ToString('o')), [System.Text.UTF8Encoding]::new($false))
$script:OwnsProfileLock = $true

# ---------------------------------------------------------------------------
# Browser acquisition
# ---------------------------------------------------------------------------

$browserSource = $null
$launchedProc  = $null

if (Test-DebugEndpoint) {
    $browserSource = 'existing-debug-port'
    $script:BrowserFailovers.Add('reuse-existing-debug-port') | Out-Null
} else {
    $candidates = @(Get-ChromiumCandidatePaths)
    foreach ($exe in $candidates) {
        $label = 'launch:' + (Split-Path -Leaf $exe)
        $procArgs = @(
            "--remote-debugging-port=$DebugPort",
            "--user-data-dir=$ProfileDir",
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-session-crashed-bubble',
            '--disable-infobars',
            '--window-size=1400,950',
            'https://chatgpt.com/'
        )
        try {
            $launchedProc = Start-Process -FilePath $exe -ArgumentList $procArgs -PassThru -WindowStyle Normal
        } catch {
            $script:BrowserFailovers.Add($label + ':spawn-failed') | Out-Null
            continue
        }
        $ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Milliseconds 1000
            try { if ($launchedProc.HasExited) { break } } catch { }
            if (Test-DebugEndpoint) { $ready = $true; break }
        }
        if ($ready) {
            $browserSource = 'launched'
            $script:BrowserFailovers.Add($label) | Out-Null
            break
        }
        $script:BrowserFailovers.Add($label + ':port-not-open') | Out-Null
        try { if (-not $launchedProc.HasExited) { Stop-Process -Id $launchedProc.Id -Force -ErrorAction SilentlyContinue } } catch { }
    }
    if (-not $browserSource) {
        Write-Result -Fields @{
            browser_source = $null; review_target_reused = $false; composer_resets = 0
            insertion_attempts = 0; sent = $false; response_received = $false
            error = 'NO_DEBUGGABLE_BROWSER: could not start any Chromium with remote debugging'
        } -ExitCode 1
    }
}

# ---------------------------------------------------------------------------
# Target (tab) management
# ---------------------------------------------------------------------------

function Get-ChatGptTargets {
    $targets = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/list" -f $DebugPort) -TimeoutSec 5
    return @($targets | Where-Object { $_.type -eq 'page' -and $_.url -match '^https://(www\.)?chatgpt\.com/' })
}

$tab = $null
$reviewTargetReused = $false
for ($i = 0; $i -lt 20; $i++) {
    $found = @(Get-ChatGptTargets)
    if ($found.Count -gt 0) { $tab = $found[0]; $reviewTargetReused = $true; break }
    Start-Sleep -Milliseconds 1000
}

if (-not $tab) {
    $enc = [uri]::EscapeDataString('https://chatgpt.com/')
    try {
        $null = Invoke-RestMethod -Method Put -Uri ("http://127.0.0.1:{0}/json/new?url={1}" -f $DebugPort, $enc) -TimeoutSec 10
    } catch {
        try { $null = Invoke-RestMethod -Uri ("http://127.0.0.1:{0}/json/new?url={1}" -f $DebugPort, $enc) -TimeoutSec 10 } catch { }
    }
    for ($i = 0; $i -lt 25; $i++) {
        $found = @(Get-ChatGptTargets)
        if ($found.Count -gt 0) { $tab = $found[0]; break }
        Start-Sleep -Milliseconds 1000
    }
}

if (-not $tab -or -not $tab.webSocketDebuggerUrl) {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = 'CHATGPT_TAB_UNAVAILABLE: no debuggable chatgpt.com page could be opened'
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# CDP websocket client
# ---------------------------------------------------------------------------

$script:CdpId = 0
$script:CdpWs = $null

function Connect-CdpTab {
    param([string]$Url)
    $ws = [System.Net.WebSockets.ClientWebSocket]::new()
    $null = $ws.ConnectAsync([Uri]$Url, [System.Threading.CancellationToken]::None).GetAwaiter().GetResult()
    $script:CdpWs = $ws
}

function Send-CdpCommand {
    param([string]$Method, [hashtable]$Params, [int]$TimeoutMs = 60000)
    $script:CdpId++
    $frame = @{ id = $script:CdpId; method = $Method; params = $Params } | ConvertTo-Json -Depth 6 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($frame)
    $ws = $script:CdpWs
    $sendCts = [System.Threading.CancellationTokenSource]::new(20000)
    [void]$ws.SendAsync([ArraySegment[byte]]::new($bytes), [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $sendCts.Token).GetAwaiter().GetResult()

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $buffer = New-Object byte[] 2097152
    $logPath = Join-Path $env:TEMP 'cdp_transport_debug.log'
    [System.IO.File]::AppendAllText($logPath, ("SENT id={0} method={1}`n" -f $script:CdpId, $Method))
    while ($sw.ElapsedMilliseconds -lt $TimeoutMs) {
        $ms = [System.IO.MemoryStream]::new()
        $endOfMessage = $false
        while (-not $endOfMessage) {
            if ($sw.ElapsedMilliseconds -ge $TimeoutMs) { throw "CDP receive timeout for $Method" }
            $seg = [ArraySegment[byte]]::new($buffer)
            $recvCts = [System.Threading.CancellationTokenSource]::new(30000)
            $res = $ws.ReceiveAsync($seg, $recvCts.Token).GetAwaiter().GetResult()
            if ($res.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
                throw "CDP websocket closed during $Method"
            }
            $ms.Write($buffer, 0, $res.Count)
            $endOfMessage = $res.EndOfMessage
        }
        $text = [System.Text.Encoding]::UTF8.GetString($ms.ToArray())
        $snippet = $text
        if ($snippet.Length -gt 400) { $snippet = $snippet.Substring(0, 400) + '...' }
        [System.IO.File]::AppendAllText($logPath, ("RECV {0}`n" -f $snippet))
        $msg = $null
        try { $msg = $text | ConvertFrom-Json } catch { continue }
        if ($msg.psobject.Properties['id'] -and $msg.id -eq $script:CdpId) {
            [System.IO.File]::AppendAllText($logPath, ("MATCHED id={0} props=[{1}]`n---`n" -f $msg.id, (($msg.psobject.Properties.Name) -join ',')))
            return $msg
        }
    }
    throw "CDP response timeout for $Method"
}

function Invoke-PageJs {
    param([string]$Js, [int]$TimeoutMs = 60000, [switch]$RetryOnDisconnect)
    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        try {
            if (-not $script:CdpWs -or $script:CdpWs.State -ne [System.Net.WebSockets.WebSocketState]::Open) {
                Connect-CdpTab -Url $script:TabUrl
            }
            $resp = Send-CdpCommand -Method 'Runtime.evaluate' -Params @{
                expression    = $Js
                returnByValue = $true
                awaitPromise  = $false
            } -TimeoutMs $TimeoutMs
            if ($resp.psobject.Properties['error'] -and $resp.error) {
                throw ("CDP protocol error: " + $resp.error.message)
            }
            $inner = $resp.result
            $hasException = ($null -ne $inner -and $null -ne $inner.psobject.Properties['exceptionDetails'] -and $null -ne $inner.exceptionDetails)
            if ($hasException) {
                $detail = ''
                $excProp = $inner.exceptionDetails
                if ($null -ne $excProp -and $null -ne $excProp.psobject.Properties['exception'] -and $null -ne $excProp.exception -and $null -ne $excProp.exception.psobject.Properties['description']) {
                    $detail = [string]$excProp.exception.description
                }
                throw ("Page JS exception: " + $detail)
            }
            $remoteObj = $null
            if ($null -ne $inner -and $null -ne $inner.psobject.Properties['result']) { $remoteObj = $inner.result }
            $valueOut = $null
            if ($null -ne $remoteObj -and $null -ne $remoteObj.psobject.Properties['value']) { $valueOut = $remoteObj.value }
            return $valueOut
        } catch {
            try { if ($script:CdpWs) { $script:CdpWs.Dispose() } } catch { }
            $script:CdpWs = $null
            if (-not $RetryOnDisconnect -or $attempt -eq 1) { throw }
            # Tab may have been closed/navigated: re-resolve then reconnect.
            $found = @(Get-ChatGptTargets)
            if ($found.Count -eq 0) { throw 'chatgpt.com tab disappeared during CDP session' }
            $script:TabUrl = $found[0].webSocketDebuggerUrl
            $script:BrowserFailovers.Add('reconnect-tab') | Out-Null
        }
    }
}

$script:TabUrl = $tab.webSocketDebuggerUrl
Connect-CdpTab -Url $script:TabUrl

# ---------------------------------------------------------------------------
# Phase 1: wait for usable composer OR detect the login wall
# ---------------------------------------------------------------------------

$statusJs = "(function(){var ed=document.querySelector('#prompt-textarea');var loginBtn=document.querySelector('button[data-testid=""login-button""]')||document.querySelector('a[href*=""/auth/login""]');var bodyTxt=document.body?document.body.innerText||'':'';if(ed)return JSON.stringify({state:'COMPOSER'});if(loginBtn)return JSON.stringify({state:'LOGIN_WALL'});if(/Log in|Sign up/.test(bodyTxt))return JSON.stringify({state:'LOGIN_WALL'});return JSON.stringify({state:'LOADING'});})()"

$pageState = 'LOADING'
$script:LastEvalError = $null
$waitDeadline = [DateTime]::UtcNow.AddSeconds(45)
while ([DateTime]::UtcNow -lt $waitDeadline) {
    $raw = $null
    try { $raw = Invoke-PageJs -Js $statusJs -TimeoutMs 20000 -RetryOnDisconnect } catch { $script:LastEvalError = $_.Exception.Message }
    if ($raw) {
        $parsed = $raw | ConvertFrom-Json
        $pageState = $parsed.state
        if ($pageState -in @('COMPOSER', 'LOGIN_WALL')) { break }
    }
    Start-Sleep -Milliseconds 1200
}

if ($pageState -eq 'LOGIN_WALL') {
    Write-Output 'LOGIN_REQUIRED: please sign in to ChatGPT in the reviewer browser window now. Waiting up to 300 seconds...'
    $loginDeadline = [DateTime]::UtcNow.AddSeconds(300)
    while ([DateTime]::UtcNow -lt $loginDeadline) {
        Start-Sleep -Seconds 4
        $raw = $null
        try { $raw = Invoke-PageJs -Js $statusJs -TimeoutMs 20000 -RetryOnDisconnect } catch { $script:LastEvalError = $_.Exception.Message }
        if ($raw) {
            $parsed = $raw | ConvertFrom-Json
            $pageState = $parsed.state
            if ($pageState -eq 'COMPOSER') { break }
            Write-Output ('login-wait: current state=' + $pageState)
        }
    }
    if ($pageState -ne 'COMPOSER') {
        Write-Result -Fields @{
            browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
            insertion_attempts = 0; sent = $false; response_received = $false
            error = 'LOGIN_REQUIRED: sign-in was not completed within the 300s wait window'
        } -ExitCode 4
    }
}
if ($pageState -ne 'COMPOSER') {
    $composerError = 'COMPOSER_NOT_FOUND: chatgpt.com loaded without a usable #prompt-textarea composer'
    if ($script:LastEvalError) { $composerError = $composerError + ' | last_eval_error: ' + $script:LastEvalError }
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = 0
        insertion_attempts = 0; sent = $false; response_received = $false
        error = $composerError
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Phase 2: reset composer
# ---------------------------------------------------------------------------

$clearJs = "(function(){var ed=document.querySelector('#prompt-textarea');if(!ed)return 'NO_EDITOR';ed.focus();document.execCommand('selectAll',false,null);document.execCommand('delete',false,null);return (ed.innerText||'').trim()===''?'CLEARED':'DIRTY';})()"

$composerResets = 0
for ($try = 0; $try -lt 3; $try++) {
    $res = Invoke-PageJs -Js $clearJs -TimeoutMs 20000 -RetryOnDisconnect
    if ($res -eq 'CLEARED') { $composerResets++; break }
    if ($res -eq 'DIRTY') { $composerResets++; continue }
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = 0; sent = $false; response_received = $false
        error = 'COMPOSER_RESET_FAILED: editor disappeared while clearing'
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Phase 3: inject the prompt line-by-line (never a bare Enter keypress)
# ---------------------------------------------------------------------------

$promptText = [System.IO.File]::ReadAllText($PromptPath)
$promptText = $promptText -replace "`r`n", "`n"
$lines = $promptText -split "`n", -1
$lastIndex = $lines.Count - 1
$insertionAttempts = 0
$beginMarker = '=== GEMINI_CHATGPT_REVIEW_BEGIN ==='
$endMarker = '=== GEMINI_CHATGPT_REVIEW_END ==='

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]
    $parts = New-Object System.Collections.Generic.List[string]
    $parts.Add("(function(){var ed=document.querySelector('#prompt-textarea');if(!ed)return 'NO_EDITOR';ed.focus();") | Out-Null
    if ($line.Length -gt 0) {
        $parts.Add("document.execCommand('insertText',false," + (ConvertTo-JsString $line) + ");") | Out-Null
    }
    if ($i -lt $lastIndex) {
        $parts.Add("document.execCommand('insertLineBreak',false,null);") | Out-Null
    }
    $parts.Add("return 'OK';})()") | Out-Null
    $res = Invoke-PageJs -Js ($parts -join '') -TimeoutMs 30000 -RetryOnDisconnect
    if ($res -ne 'OK') {
        Write-Result -Fields @{
            browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
            insertion_attempts = $insertionAttempts; sent = $false; response_received = $false
            error = ('INSERT_ABORTED: editor disappeared at line ' + ($i + 1))
        } -ExitCode 1
    }
    $insertionAttempts++
    if (($i % 60) -eq 0) {
        Write-Verbose ("injecting reviewer prompt: line {0}/{1}" -f ($i + 1), $lines.Count)
    }
}

# ---------------------------------------------------------------------------
# Phase 4: readback + marker verification BEFORE any send
# ---------------------------------------------------------------------------

# Readback must survive ProseMirror splitting the pasted content across many
# text nodes: join ALL descendant text nodes with newlines and strip zero-width
# characters so marker/SHA verification sees the logical document.
$readbackJs = "(function(){var ed=document.querySelector('#prompt-textarea');if(!ed)return '';var parts=[];(function walk(n){if(n.nodeType===3){parts.push(n.nodeValue||'');}else if(n.nodeType===1){var cs=n.childNodes;for(var i=0;i<cs.length;i++)walk(cs[i]);}})(ed);return parts.join('\n').replace(/\u200b/g,'');})()"

$composed = [string](Invoke-PageJs -Js $readbackJs -TimeoutMs 30000 -RetryOnDisconnect)

if ($ReadbackPath) {
    [System.IO.File]::WriteAllText($ReadbackPath, $composed, [System.Text.UTF8Encoding]::new($false))
}

$shaLine = ($lines | Where-Object { $_ -like 'TARGET_HEAD_SHA:*' } | Select-Object -First 1)
$verification = @{
    begin_marker_present = $composed.Contains($beginMarker)
    end_marker_present   = $composed.Contains($endMarker)
    head_sha_present     = (($null -ne $shaLine) -and $composed.Contains([string]$shaLine))
    char_ratio_ok        = ($composed.Length -ge [Math]::Floor($promptText.Length * 0.85))
}

if (-not ($verification.begin_marker_present -and $verification.end_marker_present -and $verification.head_sha_present -and $verification.char_ratio_ok)) {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = $insertionAttempts; sent = $false; response_received = $false
        error = 'MARKERS_MISSING: composed prompt failed pre-send verification; nothing was sent'
        extra = $verification
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Phase 5: click Send exactly once
# ---------------------------------------------------------------------------

$sendJs = "(function(){var btn=document.querySelector('button[data-testid=""send-button""]')||document.querySelector('button[aria-label=""Send prompt""]');if(!btn)return 'NO_BUTTON';if(btn.disabled||btn.getAttribute('aria-disabled')==='true')return 'DISABLED';btn.click();return 'CLICKED';})()"

$clickResult = [string](Invoke-PageJs -Js $sendJs -TimeoutMs 30000 -RetryOnDisconnect)
$sent = ($clickResult -eq 'CLICKED')

if (-not $sent) {
    Write-Result -Fields @{
        browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
        insertion_attempts = $insertionAttempts; sent = $false; response_received = $false
        error = ('SEND_NOT_CLICKED: send button state was ' + $clickResult)
    } -ExitCode 1
}

# After clicking Send there is exactly ONE submission. Any failure past this
# point is reported honestly; nothing is ever re-sent automatically.

# ---------------------------------------------------------------------------
# Phase 6: wait for the assistant response to finish and stabilize
# ---------------------------------------------------------------------------

$baselineJs = "(function(){return document.querySelectorAll('[data-message-author-role]').length;})()"
$baselineTurns = [int](Invoke-PageJs -Js $baselineJs -TimeoutMs 20000 -RetryOnDisconnect)

$pollJs = "(function(){var busy=!!document.querySelector('[data-testid=""stop-button""]');var turns=document.querySelectorAll('[data-message-author-role]').length;var text='';var nodes=document.querySelectorAll('[data-message-author-role=""assistant""]');if(nodes.length)text=nodes[nodes.length-1].innerText||'';return JSON.stringify({busy:busy,turns:turns,text:text});})()"

$deadline = [DateTime]::UtcNow.AddSeconds($ResponseTimeoutSec)
$prevText = $null
$responseText = $null
$responseReceived = $false

while ([DateTime]::UtcNow -lt $deadline) {
    Start-Sleep -Seconds 3
    $raw = $null
    try { $raw = Invoke-PageJs -Js $pollJs -TimeoutMs 20000 -RetryOnDisconnect } catch { Start-Sleep -Seconds 2; continue }
    if (-not $raw) { continue }
    $snap = $raw | ConvertFrom-Json
    if ((-not $snap.busy) -and ([int]$snap.turns -gt $baselineTurns) -and $snap.text -and ($snap.text -eq $prevText)) {
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
        error = ('RESPONSE_TIMEOUT: no stabilized assistant answer within {0}s' -f $ResponseTimeoutSec)
    } -ExitCode 1
}

# ---------------------------------------------------------------------------
# Phase 7: persist artifacts and report success
# ---------------------------------------------------------------------------

if ($ResponsePath) {
    [System.IO.File]::WriteAllText($ResponsePath, $responseText, [System.Text.UTF8Encoding]::new($false))
}

Write-Result -Fields @{
    browser_source = $browserSource; review_target_reused = $reviewTargetReused; composer_resets = $composerResets
    insertion_attempts = $insertionAttempts; sent = $true; response_received = $true
    error = $null
    extra = @{ response_chars = $responseText.Length }
} -ExitCode 0
