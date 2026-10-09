# 原生 Windows 的 CI 用：把固定版本的 chezmoi 與 Gitleaks 裝進一個目錄（預設 ~/.local/bin），
# 兩者都以寫死的官方 SHA-256 核對。本機已裝好時不需要執行。
# 用法：powershell -ExecutionPolicy Bypass -File .github\ci\install-windows-tools.ps1 [-Prefix DIR]
param([string]$Prefix = (Join-Path $env:USERPROFILE '.local\bin'))
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
$work = Join-Path ([System.IO.Path]::GetTempPath()) ('windows-tools-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
try {
    # chezmoi：官方 release 的 zip，SHA-256 取自 chezmoi_2.71.1_checksums.txt
    $zip = Join-Path $work 'chezmoi.zip'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -UseBasicParsing -OutFile $zip `
        -Uri 'https://github.com/twpayne/chezmoi/releases/download/v2.71.1/chezmoi_2.71.1_windows_amd64.zip'
    $hash = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLowerInvariant()
    if ($hash -ne 'efdb5ae7e8e455e8f7c1b3d7d97beb7e946d9234f58d73945b78aaf6a5e92de6') {
        Write-Output "FAIL chezmoi checksum $hash"
        exit 65
    }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $work 'chezmoi')
    Copy-Item (Join-Path $work 'chezmoi\chezmoi.exe') $Prefix -Force
    Write-Output "INSTALLED chezmoi 2.71.1 at $Prefix (sha256 verified)"
    # Gitleaks：沿用使用者也會用的安裝腳本（8.30.1，核對官方 SHA-256）
    $ErrorActionPreference = 'Continue'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'setup\install-gitleaks.ps1') -Prefix $Prefix
    $ErrorActionPreference = 'Stop'
    if ($LASTEXITCODE -ne 0) { Write-Output 'FAIL install-gitleaks.ps1'; exit $LASTEXITCODE }
} finally {
    Remove-Item -Recurse -Force -Path $work -ErrorAction SilentlyContinue
}
