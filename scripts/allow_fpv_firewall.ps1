# Allow MuJoCo FPV MJPEG TCP 8765 into Windows/WSL (Quest Browser).
# Run in PowerShell **as Administrator**:
#   powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\allow_fpv_firewall.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$port = 8765
$ruleName = "SONIC MuJoCo FPV TCP 8765"

$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Rule already exists: $ruleName"
    Get-NetFirewallPortFilter -AssociatedNetFirewallRule $existing | Format-List
    exit 0
}

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Description "MuJoCo FPV MJPEG for Quest Browser (WSL run_sim_t1_fpv_quest.sh)" `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $port `
    -Profile Domain,Private,Public | Out-Null

Write-Host "OK: inbound TCP $port allowed ($ruleName)"
Write-Host "Quest Browser: http://<PC-WiFi-IP>:$port/  (same WiFi as PC)"
