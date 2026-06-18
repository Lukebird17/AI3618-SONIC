#!/usr/bin/env bash
# WSL: start Linux adb and connect Meta Quest over WiFi (after Mac/Windows USB: adb tcpip 5555).
set -euo pipefail

QUEST_IP="${1:-192.168.0.101}"
QUEST_PORT="${2:-5555}"

# WSL uses its own adb daemon on Linux localhost:5037 — do not point at Windows.
unset ADB_SERVER_SOCKET

echo "[quest_adb] Starting WSL adb server..."
adb kill-server 2>/dev/null || true
adb start-server

echo "[quest_adb] Connecting to ${QUEST_IP}:${QUEST_PORT} ..."
adb connect "${QUEST_IP}:${QUEST_PORT}"

echo
adb devices -l

if adb devices | awk 'NR>1 && $2=="device"{found=1} END{exit !found}'; then
  echo "[quest_adb] OK — Quest reachable from WSL."
  exit 0
fi

echo "[quest_adb] No device yet. Enable WiFi adb first:" >&2
echo "  USB + trust → adb devices (must show 'device')" >&2
echo "  adb tcpip 5555" >&2
echo "  adb connect ${QUEST_IP}:${QUEST_PORT}" >&2
exit 1
