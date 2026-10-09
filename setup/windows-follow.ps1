# 原生 Windows 的跟隨模式：只把私有 dotfiles 的共用設定套用到 ~/.claude，不部署同步引擎、不修改或發布規則。
# 要在這台完整同步（記錄與發布）就照 docs/wsl.md 第 8 節經 Git Bash 部署引擎，不用這個腳本。
#
# 用法（PowerShell）：
#   powershell -ExecutionPolicy Bypass -File setup\windows-follow.ps1
#       預覽：fetch、以 Gitleaks 掃描遠端最新內容、顯示 ~/.claude 的 diff。不修改 source 或 ~/.claude。
#   powershell -ExecutionPolicy Bypass -File setup\windows-follow.ps1 -Apply -Expect <REMOTE_HEAD>
#       只套用預覽時看到的那個版本；遠端在這之間又有變動就拒絕。
param(
    [switch]$Apply,
    [string]$Expect = ''
)
$ErrorActionPreference = 'Stop'
$GitleaksVersion = '8.30.1'
$UserHome = $env:USERPROFILE
$Claude = Join-Path $UserHome '.claude'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Stop-Follow([string]$Message, [int]$Code = 1) {
    Write-Output "FAIL $Message"
    exit $Code
}

function Find-Tool([string]$Name) {
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { return $command.Source }
    $local = Join-Path $UserHome ".local\bin\$Name.exe"
    if (Test-Path $local) { return $local }
    return $null
}

function Invoke-Tool([string]$FilePath, [string[]]$Arguments) {
    # 直接以 Process 執行：取得確切的 exit code 與輸出；stdin 立即關閉，互動提示只會拿到 EOF，不會卡住
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $quoted = foreach ($argument in $Arguments) {
        if ($argument -eq '' -or $argument -match '[\s"]') { '"' + ($argument -replace '"', '\"') + '"' } else { $argument }
    }
    $psi.Arguments = $quoted -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    $process = [System.Diagnostics.Process]::Start($psi)
    $process.StandardInput.Close()
    $out = $process.StandardOutput.ReadToEndAsync()
    $err = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    return [pscustomobject]@{ Code = $process.ExitCode; Out = $out.Result; Err = $err.Result }
}

function Invoke-Git([string[]]$Arguments) {
    $result = Invoke-Tool $script:Git (@('-C', $script:Source) + $Arguments)
    if ($result.Code -ne 0) { Stop-Follow ('git ' + ($Arguments -join ' ') + ' failed: ' + $result.Err.Trim()) 70 }
    return $result.Out.Trim()
}

if ($Apply -and -not $Expect) { Stop-Follow 'usage: -Apply needs -Expect <REMOTE_HEAD> from the preview' 64 }

# 1. 前置檢查：工具、未部署引擎、chezmoi source 存在
$script:Git = Find-Tool 'git'
if (-not $script:Git) { Stop-Follow 'git not found -> install Git for Windows' 69 }
$chezmoi = Find-Tool 'chezmoi'
if (-not $chezmoi) { Stop-Follow 'chezmoi not found -> install chezmoi 2.71 (docs/wsl.md, native Windows follower)' 69 }
$gitleaks = Find-Tool 'gitleaks'
if (-not $gitleaks) { Stop-Follow 'gitleaks not found -> powershell -ExecutionPolicy Bypass -File setup\install-gitleaks.ps1' 69 }
$found = (Invoke-Tool $gitleaks @('version')).Out.Trim()
if ($found -ne $GitleaksVersion) { Stop-Follow "gitleaks $found at $gitleaks -> need $GitleaksVersion (setup\install-gitleaks.ps1)" 69 }
foreach ($relative in @('.config\ai-agent\bin\sync.sh', '.config\ai-agent\sync.local.json')) {
    if (Test-Path (Join-Path $UserHome $relative)) {
        Stop-Follow ("~/" + ($relative -replace '\\', '/') + ' exists: the engine is deployed on this host, so it syncs fully through Git Bash (docs/wsl.md section 8) -> use sh ~/.config/ai-agent/bin/sync.sh instead of the follower, or remove ~/.config/ai-agent to follow only') 65
    }
}
$located = Invoke-Tool $chezmoi @('source-path')
$script:Source = $located.Out.Trim()
if ($located.Code -ne 0 -or -not (Test-Path (Join-Path $script:Source '.git'))) {
    Stop-Follow 'chezmoi source not initialized -> chezmoi init <your private dotfiles remote>' 65
}

# 2. source 必須乾淨；只 fetch，確認可以 fast-forward，並綁定預覽時的版本
if (Invoke-Git @('status', '--porcelain')) {
    Stop-Follow 'the chezmoi source has local changes -> this host only follows; record rules in WSL or macOS/Linux' 66
}
Invoke-Git @('fetch', '--quiet') | Out-Null
$remote = Invoke-Git @('rev-parse', '@{u}')
if ((Invoke-Tool $script:Git @('-C', $script:Source, 'merge-base', '--is-ancestor', 'HEAD', '@{u}')).Code -ne 0) {
    Stop-Follow 'the source has commits the remote lacks -> this host never publishes; inspect it manually' 66
}
$incoming = @(Invoke-Git @('log', '--oneline', 'HEAD..@{u}') -split "`n" | Where-Object { $_ })
Write-Output "REMOTE_HEAD: $remote"
Write-Output "INCOMING: $($incoming.Count)"
foreach ($line in $incoming) { Write-Output "  $line" }
if ($Apply -and -not ($Expect.Length -ge 7 -and $remote.StartsWith($Expect))) {
    Stop-Follow "the remote moved since the preview (expected $Expect, now $remote) -> run the preview again" 68
}

$work = Join-Path ([System.IO.Path]::GetTempPath()) ('windows-follow-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    # 3. 先掃描再合併：匯出遠端版本，用與引擎相同的方式掃描（中性檔名、預設規則、不採用 allowlist、遮蔽內容）
    $zip = Join-Path $work 'tree.zip'
    Invoke-Git @('archive', '--format=zip', '-o', $zip, $remote) | Out-Null
    $tree = Join-Path $work 'tree'
    Expand-Archive -Path $zip -DestinationPath $tree
    $payload = Join-Path $work 'payload'
    New-Item -ItemType Directory -Path $payload | Out-Null
    $map = @{}
    foreach ($file in (Get-ChildItem -Path $tree -Recurse -File -Force)) {
        $name = '{0:D4}.txt' -f $map.Count
        Copy-Item -LiteralPath $file.FullName -Destination (Join-Path $payload $name)
        $map[$name] = $file.FullName.Substring($tree.Length + 1) -replace '\\', '/'
    }
    $config = Join-Path $work 'gitleaks.toml'
    Set-Content -Path $config -Value "[extend]`nuseDefault = true" -Encoding ASCII
    $ignore = Join-Path $work 'empty.ignore'
    Set-Content -Path $ignore -Value '' -Encoding ASCII
    $report = Join-Path $work 'report.json'
    $scan = Invoke-Tool $gitleaks @('dir', $payload, '--config', $config, '--gitleaks-ignore-path', $ignore,
        '--ignore-gitleaks-allow', '--exit-code', '10', '--redact=100', '--no-banner', '--no-color',
        '--log-level', 'error', '--report-format', 'json', '--report-path', $report,
        '--max-target-megabytes', '0', '--max-decode-depth', '5', '--max-archive-depth', '0', '--timeout', '90')
    if ($scan.Code -eq 10) {
        foreach ($finding in (Get-Content -Raw -Path $report | ConvertFrom-Json)) {
            Write-Output ('FINDING: {0} rule={1} line={2}' -f $map[(Split-Path -Leaf $finding.File)], $finding.RuleID, $finding.StartLine)
        }
        Stop-Follow 'BLOCKED_SECRET: the remote contains a possible secret; nothing applied, values withheld' 67
    }
    if ($scan.Code -ne 0) { Stop-Follow "SCANNER_ERROR: gitleaks exit $($scan.Code); nothing applied" 70 }
    Write-Output "OK   scan: $($map.Count) files clean (gitleaks $GitleaksVersion)"

    # 4. 預覽用匯出的版本產生 diff，完全不動 source；套用時才 fast-forward
    if ($Apply -and $incoming.Count -gt 0) { Invoke-Git @('merge', '--ff-only', '--quiet', $remote) | Out-Null }
    $diffSource = if ($Apply) { $script:Source } else { $tree }
    $diff = Invoke-Tool $chezmoi @('--source', $diffSource, 'diff', '--no-pager', '--no-tty', '--recursive', $Claude)
    if ($diff.Code -ne 0) { Stop-Follow ('chezmoi diff failed: ' + $diff.Err.Trim()) 70 }
    if (-not $diff.Out.Trim()) {
        Write-Output 'NO_CHANGES: ~/.claude already matches REMOTE_HEAD'
        exit 0
    }
    Write-Output $diff.Out.TrimEnd()
    if (-not $Apply) {
        Write-Output 'PREVIEW ONLY: nothing was changed. To apply exactly this version:'
        Write-Output "  powershell -ExecutionPolicy Bypass -File setup\windows-follow.ps1 -Apply -Expect $remote"
        exit 0
    }

    # 5. 只套用 ~/.claude；檔案在本機被改過時 chezmoi 會以 EOF 停下，不覆寫
    $applied = Invoke-Tool $chezmoi @('apply', '--no-tty', '--recursive', $Claude)
    if ($applied.Code -ne 0) {
        if ($applied.Err -match 'has changed since chezmoi last wrote it') {
            Stop-Follow ('a file under ~/.claude was edited locally, so apply stopped: ' + (($applied.Err.Trim() -split "`n")[0]) + ' -> review that file, then decide whether to overwrite it') 66
        }
        Stop-Follow ('chezmoi apply failed: ' + $applied.Err.Trim()) 70
    }

    # 6. 驗證：~/.claude 與 source 一致，且沒有部署引擎
    $left = Invoke-Tool $chezmoi @('diff', '--no-pager', '--no-tty', '--recursive', $Claude)
    if ($left.Code -ne 0 -or $left.Out.Trim()) { Stop-Follow '~/.claude still differs from the source after apply' 70 }
    if (Test-Path (Join-Path $UserHome '.config\ai-agent')) { Stop-Follow '~/.config/ai-agent appeared; it must not be deployed on native Windows' 70 }
    Write-Output "OK: ~/.claude matches $remote"
} finally {
    Remove-Item -Recurse -Force -Path $work -ErrorAction SilentlyContinue
}
