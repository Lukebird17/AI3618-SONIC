#!/usr/bin/env bash
# Free SONIC ZMQ ports before restarting deploy / manager.
set -euo pipefail

echo "[kill_sonic_zmq] Stopping processes on ports 5556 / 5557 ..."

for port in 5556 5557; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" 2>/dev/null || true
  fi
done

pkill -f 'g1_deploy_onnx' 2>/dev/null || true
pkill -f 'deploy.sh' 2>/dev/null || true
sleep 1

if command -v ss >/dev/null 2>&1; then
  ss -tlnp 2>/dev/null | grep -E ':5556|:5557' || echo "[kill_sonic_zmq] Ports 5556/5557 are free."
else
  echo "[kill_sonic_zmq] Done."
fi
