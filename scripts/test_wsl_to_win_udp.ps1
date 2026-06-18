# Test which source IP WSL uses to reach Windows UDP listener.
# Run in PowerShell (no admin): powershell -File C:\File\vr\scripts\test_wsl_to_win_udp.ps1
# Then from WSL: python3 -c "import socket; s=socket.socket(...); s.sendto(b'hi',('127.0.0.1',17773))" etc.

$port = 17773
$udp = New-Object System.Net.Sockets.UdpClient
$udp.Client.SetSocketOption([Net.Sockets.SocketOptionLevel]::Socket, [Net.Sockets.SocketOptionName]::ReuseAddress, $true)
$udp.Client.Bind([Net.IPEndPoint]::new([IPAddress]::Any, $port))
$udp.Client.ReceiveTimeout = 12000
Write-Host "Listening UDP $port on Windows..."
$ep = New-Object System.Net.IPEndPoint([IPAddress]::Any, 0)
try {
    $b = $udp.Receive([ref]$ep)
    $txt = [Text.Encoding]::UTF8.GetString($b)
    Write-Host "OK from $($ep.Address):$($ep.Port) len=$($b.Length) data=$txt"
} catch {
    Write-Host "TIMEOUT (no packet in 12s)"
}
$udp.Close()
