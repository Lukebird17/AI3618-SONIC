# Expose WSL MuJoCo FPV (8765) to PC LAN + Quest Browser.
# WSL mirrored: Windows localhost already reaches WSL; LAN IPs need portproxy.
#
# Run in PowerShell **as Administrator** (once per boot, or after reboot):
#   powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\setup_fpv_quest_network.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$port = 8765
$connectHost = "127.0.0.1"
$ruleName = "SONIC MuJoCo FPV TCP 8765"
$listenAddresses = @("0.0.0.0")

Write-Host "Checking WSL FPV on ${connectHost}:${port} ..."
$tcp = Test-NetConnection -ComputerName $connectHost -Port $port -WarningAction SilentlyContinue
if (-not $tcp.TcpTestSucceeded) {
    Write-Host "ERROR: nothing listening on ${connectHost}:${port}." -ForegroundColor Red
    Write-Host "Start T1 first: ~/vr/scripts/run_sim_t1_fpv_quest.sh" -ForegroundColor Yellow
    exit 1
}

foreach ($listen in $listenAddresses) {
    netsh interface portproxy delete v4tov4 listenaddress=$listen listenport=$port 2>$null | Out-Null
    netsh interface portproxy add v4tov4 listenaddress=$listen listenport=$port connectaddress=$connectHost connectport=$port | Out-Null
    Write-Host "portproxy ${listen}:${port} -> ${connectHost}:${port}"
}

$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if (-not $existing) {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Description "MuJoCo FPV MJPEG for PC/Quest Browser" `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $port `
        -Profile Domain,Private,Public | Out-Null
    Write-Host "firewall: inbound TCP $port allowed"
} else {
    Write-Host "firewall: rule already exists ($ruleName)"
}

$wifiIp = (
    Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.InterfaceAlias -match 'WLAN|Wi-Fi|WiFi' -and $_.IPAddress -notlike '169.*' } |
    Select-Object -First 1 -ExpandProperty IPAddress
)

Write-Host ""
Write-Host "OK. Open in browser:" -ForegroundColor Green
Write-Host "  PC:    http://localhost:${port}/"
if ($wifiIp) {
    Write-Host "  Quest: http://${wifiIp}:${port}/  (same WiFi as PC)"
} else {
    Write-Host "  Quest: http://<PC-WiFi-IP>:${port}/"
}
Write-Host ""
Write-Host "Verify on PC:"
Write-Host "  curl http://localhost:${port}/"
if ($wifiIp) {
    Write-Host "  curl http://${wifiIp}:${port}/"
}
