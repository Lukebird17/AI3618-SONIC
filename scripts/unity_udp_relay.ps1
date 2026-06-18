# WSL bridge (TCP) -> Windows Unity (UDP 17771).
# Mirrored WSL cannot send UDP to Windows; Windows CAN connect TCP to WSL.
#
# 1) WSL T4: python -m sonic_bridge.run_bridge ... --tcp-relay-port 17782
# 2) Windows Unity: Play
# 3) Run this script (no admin):
#    powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\unity_udp_relay.ps1

$ErrorActionPreference = "Stop"

$tcpHost = "127.0.0.1"
$tcpPort = 17782
$udpHost = "127.0.0.1"
$udpPort = 17771

Write-Host "Unity UDP relay: TCP ${tcpHost}:${tcpPort} -> UDP ${udpHost}:${udpPort}"
Write-Host "Start WSL bridge with --tcp-relay-port $tcpPort first, then Unity Play."
Write-Host ""

while ($true) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect($tcpHost, $tcpPort)
        $stream = $tcp.GetStream()
        $udp = New-Object System.Net.Sockets.UdpClient
        $udpTarget = New-Object System.Net.IPEndPoint([IPAddress]::Parse($udpHost), $udpPort)
        Write-Host "Connected to WSL bridge relay. Forwarding to Unity..."

        $buffer = New-Object byte[] 65536
        $carry = ""

        while ($tcp.Connected) {
            $read = $stream.Read($buffer, 0, $buffer.Length)
            if ($read -le 0) { break }
            $carry += [Text.Encoding]::UTF8.GetString($buffer, 0, $read)
            while ($carry.Contains("`n")) {
                $idx = $carry.IndexOf("`n")
                $line = $carry.Substring(0, $idx).Trim()
                $carry = $carry.Substring($idx + 1)
                if ($line.Length -eq 0) { continue }
                $bytes = [Text.Encoding]::UTF8.GetBytes($line)
                [void]$udp.Send($bytes, $bytes.Length, $udpTarget)
            }
        }
    } catch {
        Write-Host "Relay disconnected: $($_.Exception.Message). Retry in 2s..."
        Start-Sleep -Seconds 2
    } finally {
        if ($udp) { $udp.Close() }
        if ($tcp) { $tcp.Close() }
    }
}
