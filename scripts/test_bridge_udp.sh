#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/File/vr/sonic-bridge
pip3 install -q -e .
timeout 4 python3 -m sonic_bridge.standalone_demo &
sleep 1
python3 << 'PY'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(("0.0.0.0", 17771))
s.settimeout(3)
data, _ = s.recvfrom(4096)
print("UDP OK", len(data), "bytes")
print(data[:160].decode())
PY
pkill -f standalone_demo 2>/dev/null || true
