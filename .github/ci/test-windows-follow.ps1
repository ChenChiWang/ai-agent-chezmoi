# setup/windows-follow.ps1 的端對端測試：暫存的 HOME 與本機假 remote，不碰真實環境。
# CI 會先安裝固定版本的 chezmoi 與 Gitleaks；本機已裝好時可加 -SkipInstall。
param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$root = Join-Path ([System.IO.Path]::GetTempPath()) ('follow-test-' + [guid]::NewGuid().ToString('N'))
$tools = Join-Path $root 'tools'
New-Item -ItemType Directory -Path $tools | Out-Null

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw "ASSERT: $Message" }
}

function Invoke-Follow([string[]]$Arguments) {
    # PowerShell 5.1 在 Stop 模式下會把原生程式的 stderr 當成例外；外部指令一律只看 exit code
    $ErrorActionPreference = 'Continue'
    $output = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'setup\windows-follow.ps1') @Arguments 2>&1 | Out-String
    return [pscustomobject]@{ Code = $LASTEXITCODE; Out = $output }
}

function Invoke-Git([string[]]$Arguments) {
    $ErrorActionPreference = 'Continue'
    $output = & git @Arguments 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed: $output" }
    return $output.Trim()
}

try {
    if (-not $SkipInstall) {
        # chezmoi：官方 release 的 zip，以寫死的 SHA-256 核對（取自 chezmoi_2.71.1_checksums.txt）
        $zip = Join-Path $root 'chezmoi.zip'
        Invoke-WebRequest -UseBasicParsing -OutFile $zip `
            -Uri 'https://github.com/twpayne/chezmoi/releases/download/v2.71.1/chezmoi_2.71.1_windows_amd64.zip'
        $hash = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLowerInvariant()
        Assert-True ($hash -eq 'efdb5ae7e8e455e8f7c1b3d7d97beb7e946d9234f58d73945b78aaf6a5e92de6') "chezmoi checksum $hash"
        Expand-Archive -Path $zip -DestinationPath (Join-Path $root 'chezmoi')
        Copy-Item (Join-Path $root 'chezmoi\chezmoi.exe') $tools
        $ErrorActionPreference = 'Continue'
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'setup\install-gitleaks.ps1') -Prefix $tools
        $ErrorActionPreference = 'Stop'
        Assert-True ($LASTEXITCODE -eq 0) 'install-gitleaks.ps1 failed'
        $env:PATH = "$tools;$env:PATH"
    }

    # 隔離的 HOME 與 git 設定
    $fixtureHome = Join-Path $root 'home'
    New-Item -ItemType Directory -Path $fixtureHome | Out-Null
    $env:USERPROFILE = $fixtureHome
    $env:HOME = $fixtureHome
    $env:GIT_CONFIG_NOSYSTEM = '1'
    $env:GIT_CONFIG_GLOBAL = Join-Path $root 'gitconfig'
    Set-Content -Path $env:GIT_CONFIG_GLOBAL -Value '' -Encoding ASCII
    $env:GIT_AUTHOR_NAME = 'Fixture'; $env:GIT_AUTHOR_EMAIL = 'fixture@example.test'
    $env:GIT_COMMITTER_NAME = 'Fixture'; $env:GIT_COMMITTER_EMAIL = 'fixture@example.test'

    # 以範本建立假的私有 remote，再用 chezmoi init 取得 source
    $work = Join-Path $root 'work'
    $remote = Join-Path $root 'remote.git'
    Copy-Item -Recurse -Path (Join-Path $repo 'examples\chezmoi') -Destination $work
    Invoke-Git @('-C', $work, 'init', '-q', '-b', 'main') | Out-Null
    Invoke-Git @('-C', $work, 'add', '.') | Out-Null
    Invoke-Git @('-C', $work, 'commit', '-q', '-m', 'fixture baseline') | Out-Null
    Invoke-Git @('clone', '-q', '--bare', $work, $remote) | Out-Null
    Invoke-Git @('-C', $work, 'remote', 'add', 'origin', $remote) | Out-Null
    $ErrorActionPreference = 'Continue'
    & chezmoi init --no-tty $remote 2>&1 | Out-Null
    $ErrorActionPreference = 'Stop'
    Assert-True ($LASTEXITCODE -eq 0) 'chezmoi init failed'
    $source = Join-Path $fixtureHome '.local\share\chezmoi'
    $claude = Join-Path $fixtureHome '.claude'
    $instructions = '.chezmoitemplates/ai/shared/instructions.md'

    # 第一次預覽：顯示 diff，不建立 ~/.claude
    $r = Invoke-Follow @()
    Assert-True ($r.Code -eq 0 -and $r.Out -match 'PREVIEW ONLY') "first preview: $($r.Out)"
    Assert-True (-not (Test-Path $claude)) 'preview created ~/.claude'
    $head = ([regex]::Match($r.Out, 'REMOTE_HEAD: ([0-9a-f]{40})')).Groups[1].Value
    Assert-True ($head.Length -eq 40) 'no REMOTE_HEAD in preview'

    # 錯的 -Expect：拒絕
    $r = Invoke-Follow @('-Apply', '-Expect', '0000000')
    Assert-True ($r.Code -eq 68 -and -not (Test-Path $claude)) "wrong expect: $($r.Out)"

    # 正確的 -Expect：只部署 ~/.claude，不部署引擎
    $r = Invoke-Follow @('-Apply', '-Expect', $head)
    Assert-True ($r.Code -eq 0 -and $r.Out -match 'OK: ~/.claude matches') "apply: $($r.Out)"
    Assert-True (Test-Path (Join-Path $claude 'CLAUDE.md')) 'CLAUDE.md not deployed'
    Assert-True (-not (Test-Path (Join-Path $fixtureHome '.config\ai-agent'))) 'engine was deployed'
    $r = Invoke-Follow @()
    Assert-True ($r.Code -eq 0 -and $r.Out -match 'NO_CHANGES') "second preview: $($r.Out)"

    # 遠端有新 commit：預覽不合併 source，套用後內容更新
    Add-Content -Path (Join-Path $work $instructions) -Value "`nWindows follower incoming rule.`n" -Encoding UTF8
    Invoke-Git @('-C', $work, 'commit', '-q', '-am', 'incoming rule') | Out-Null
    Invoke-Git @('-C', $work, 'push', '-q', 'origin', 'main') | Out-Null
    $before = Invoke-Git @('-C', $source, 'rev-parse', 'HEAD')
    $r = Invoke-Follow @()
    Assert-True ($r.Code -eq 0 -and $r.Out -match 'INCOMING: 1' -and $r.Out -match 'Windows follower incoming rule') "incoming preview: $($r.Out)"
    Assert-True ((Invoke-Git @('-C', $source, 'rev-parse', 'HEAD')) -eq $before) 'preview moved the source'
    $head = ([regex]::Match($r.Out, 'REMOTE_HEAD: ([0-9a-f]{40})')).Groups[1].Value
    $r = Invoke-Follow @('-Apply', '-Expect', $head)
    Assert-True ($r.Code -eq 0) "incoming apply: $($r.Out)"
    Assert-True ((Get-Content -Raw (Join-Path $claude 'CLAUDE.md')) -match 'Windows follower incoming rule') 'incoming rule not applied'

    # 遠端被植入假秘密：擋下，~/.claude 與 source 都不變（token 在執行時才組出）
    $token = 'ghp_' + ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')).Substring(0, 36)
    Add-Content -Path (Join-Path $work $instructions) -Value "`nexample = $token`n" -Encoding UTF8
    Invoke-Git @('-C', $work, 'commit', '-q', '-am', 'synthetic secret') | Out-Null
    Invoke-Git @('-C', $work, 'push', '-q', 'origin', 'main') | Out-Null
    $claudeBefore = Get-Content -Raw (Join-Path $claude 'CLAUDE.md')
    $before = Invoke-Git @('-C', $source, 'rev-parse', 'HEAD')
    $r = Invoke-Follow @()
    Assert-True ($r.Code -eq 67 -and $r.Out -match "FINDING: $([regex]::Escape($instructions))") "secret preview: $($r.Out)"
    Assert-True ($r.Out -notmatch [regex]::Escape($token)) 'secret value leaked into output'
    Assert-True ((Get-Content -Raw (Join-Path $claude 'CLAUDE.md')) -eq $claudeBefore) '~/.claude changed despite secret'
    Assert-True ((Invoke-Git @('-C', $source, 'rev-parse', 'HEAD')) -eq $before) 'source moved despite secret'
    Invoke-Git @('-C', $work, 'revert', '--no-edit', 'HEAD') | Out-Null
    Invoke-Git @('-C', $work, 'push', '-q', 'origin', 'main') | Out-Null

    # source 有本地修改：這台只跟隨，停下來
    Add-Content -Path (Join-Path $source $instructions) -Value 'local edit' -Encoding UTF8
    $r = Invoke-Follow @()
    Assert-True ($r.Code -eq 66) "local change: $($r.Out)"
    Invoke-Git @('-C', $source, 'checkout', '--', $instructions) | Out-Null

    # 已部署引擎：停下來說明
    New-Item -ItemType Directory -Force -Path (Join-Path $fixtureHome '.config\ai-agent\bin') | Out-Null
    Set-Content -Path (Join-Path $fixtureHome '.config\ai-agent\bin\sync.sh') -Value '' -Encoding ASCII
    $r = Invoke-Follow @()
    Assert-True ($r.Code -eq 65 -and $r.Out -match 'the engine is deployed on this host') "engine guard: $($r.Out)"

    Write-Output 'OK windows-follow end-to-end checks'
} finally {
    Remove-Item -Recurse -Force -Path $root -ErrorAction SilentlyContinue
}
