# 安裝固定版本的 Gitleaks 到使用者目錄（預設 ~/.local/bin），不需要系統管理員權限。
# 下載後以寫死的官方 SHA-256 核對，再確認二進位回報的版本，最後才放到目的地。
# 用法：powershell -ExecutionPolicy Bypass -File setup\install-gitleaks.ps1 [-Prefix DIR] [-Force]
param(
    [string]$Prefix = (Join-Path $env:USERPROFILE '.local\bin'),
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$Version = '8.30.1'
# 取自官方 gitleaks_8.30.1_checksums.txt
$Sums = @{
    'x64'   = 'd29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e'
    'arm64' = 'b95f5e4f5c425cedca7ee203d9afd29597e692c4924a12ed42f970537c72cc0f'
}

function Stop-Install([string]$Message, [int]$Code = 1) {
    Write-Output "FAIL $Message"
    exit $Code
}

$arch = switch ($env:PROCESSOR_ARCHITECTURE) {
    'AMD64' { 'x64' }
    'ARM64' { 'arm64' }
    default { Stop-Install "unsupported architecture $($env:PROCESSOR_ARCHITECTURE); install gitleaks $Version manually" 69 }
}
$target = Join-Path $Prefix 'gitleaks.exe'
if (Test-Path $target) {
    $current = (& $target version 2>$null | Out-String).Trim()
    if ($current -eq $Version) {
        Write-Output "OK gitleaks $Version already installed at $target"
        exit 0
    }
    if (-not $Force) { Stop-Install "$target exists with version '$current'; rerun with -Force to replace it" 73 }
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('gitleaks-install-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $zip = Join-Path $tmp 'gitleaks.zip'
    $url = "https://github.com/gitleaks/gitleaks/releases/download/v$Version/gitleaks_${Version}_windows_$arch.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    try {
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -TimeoutSec 120
    } catch {
        Stop-Install "download failed: $url" 71
    }
    $actual = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLowerInvariant()
    if ($actual -ne $Sums[$arch]) { Stop-Install "checksum mismatch for windows_${arch}: expected $($Sums[$arch]) got $actual; archive discarded" 65 }
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp 'out')
    $binary = Join-Path $tmp 'out\gitleaks.exe'
    if (-not (Test-Path $binary)) { Stop-Install 'archive does not contain gitleaks.exe' 65 }
    $reported = (& $binary version 2>$null | Out-String).Trim()
    if ($reported -ne $Version) { Stop-Install "downloaded binary reports '$reported', expected $Version" 65 }
    New-Item -ItemType Directory -Force -Path $Prefix | Out-Null
    Move-Item -Force -Path $binary -Destination $target
    Write-Output "INSTALLED gitleaks $Version at $target (sha256 verified)"
    if (-not (($env:PATH -split ';') -contains $Prefix)) {
        Write-Output "NOTE add $Prefix to PATH (for example in System Properties > Environment Variables)"
    }
} finally {
    Remove-Item -Recurse -Force -Path $tmp -ErrorAction SilentlyContinue
}
