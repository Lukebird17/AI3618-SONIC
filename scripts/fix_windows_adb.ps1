# Fix Windows adb "could not read ok from ADB Server" on port 5037.
# Root cause on this machine: default tcp:5037 fails; tcp:5038 works.
# Run in PowerShell (no admin required):
#   powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\fix_windows_adb.ps1

$ErrorActionPreference = "Stop"

$port = "5038"
[Environment]::SetEnvironmentVariable("ANDROID_ADB_SERVER_PORT", $port, "User")
Remove-Item Env:ADB_SERVER_SOCKET -ErrorAction SilentlyContinue
$env:ANDROID_ADB_SERVER_PORT = $port

$adb = Get-Command adb -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue
if (-not $adb) {
    $wingetAdb = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe"
    if (Test-Path $wingetAdb) { $adb = $wingetAdb }
}
if (-not $adb) {
    Write-Error "adb not found. Install: winget install Google.PlatformTools"
}

Write-Host "Using adb: $adb"
Write-Host "ANDROID_ADB_SERVER_PORT=$port (User env, persistent)"
Write-Host ""

& $adb kill-server 2>$null
& $adb start-server
& $adb devices

Write-Host ""
Write-Host "If List of devices attached is empty, Quest WiFi adb is not enabled yet."
Write-Host "USB trust -> adb tcpip 5555 -> adb connect <quest-ip>:5555"
