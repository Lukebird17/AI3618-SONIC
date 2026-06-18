# Allow sonic-bridge UDP 17771 into Windows (Unity Editor Play).
# Run in PowerShell **as Administrator**:
#   powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\allow_unity_udp_firewall.ps1
#
# WSL T4 sends: python -m sonic_bridge.run_bridge --udp-host 192.168.0.108

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$port = 17771
$ruleName = "SONIC Quest Mirror UDP 17771"

$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Rule already exists: $ruleName"
    Get-NetFirewallPortFilter -AssociatedNetFirewallRule $existing | Format-List
    exit 0
}

New-NetFirewallRule `
    -DisplayName $ruleName `
    -Description "sonic-bridge -> Unity UdpStateReceiver (Quest Mirror)" `
    -Direction Inbound `
    -Action Allow `
    -Protocol UDP `
    -LocalPort $port `
    -Profile Domain,Private,Public | Out-Null

Write-Host "OK: inbound UDP $port allowed ($ruleName)"
Write-Host "Unity Play should show data instead of 'Waiting for UDP 17771...'"
