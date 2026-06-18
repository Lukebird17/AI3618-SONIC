# Sync quest-mirror-unity (inner) and open in Unity Hub — Windows PowerShell
# Usage: powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\setup_quest_mirror_unity.ps1

$ErrorActionPreference = "Stop"

$VrRoot = if (Test-Path "C:\File\vr") { "C:\File\vr" } else { Split-Path $PSScriptRoot -Parent }
$InnerProject = Join-Path $VrRoot "quest-mirror-unity\quest mirror unity"
$WslInner = "\\wsl$\Ubuntu\home\leon_\vr\quest-mirror-unity\quest mirror unity"

function Sync-From-Wsl {
    param([string]$Src, [string]$Dst)
    if (-not (Test-Path $Src)) {
        Write-Host "[WARN] WSL source not found: $Src"
        return $false
    }
    Write-Host "==> robocopy $Src -> $Dst"
    New-Item -ItemType Directory -Force -Path $Dst | Out-Null
    robocopy $Src $Dst /MIR /XD Library Logs Temp UserSettings .codely-cli /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    return $true
}

# Prefer WSL sync when available (latest code from Linux side)
$synced = $false
if (Test-Path $WslInner) {
    $synced = Sync-From-Wsl -Src $WslInner -Dst $InnerProject
}

if (-not $synced) {
    Write-Host "[INFO] Using local WSL copy under $VrRoot (run sync_unity_to_windows.sh from WSL if stale)"
}

if (-not (Test-Path $InnerProject)) {
    Write-Host "[ERROR] Unity project not found: $InnerProject"
    Write-Host "        Run from WSL: ~/vr/scripts/sync_unity_to_windows.sh"
    exit 1
}

$UnityHub = @(
    "${env:ProgramFiles}\Unity Hub\Unity Hub.exe",
    "${env:LOCALAPPDATA}\Programs\Unity Hub\Unity Hub.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

Write-Host ""
Write-Host "=== OPEN THIS PROJECT (inner folder) ==="
Write-Host $InnerProject
Write-Host ""
Write-Host "In Unity Editor menu:"
Write-Host "  Sonic Quest Mirror -> Build Everything (Complete — Meshes + Scene)"
Write-Host ""
Write-Host "NOT: Setup Scene (Editor UDP Test) — that is the OLD script-only copy."
Write-Host ""

if ($UnityHub) {
    Start-Process $UnityHub -ArgumentList @("--", "--projectPath", $InnerProject)
} else {
    Write-Host "Unity Hub not found. Add project manually: $InnerProject"
}
