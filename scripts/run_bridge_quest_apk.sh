#!/usr/bin/env bash
# T4 → Quest 头显内 Unity APK（UDP 直连，不需要 Quest Link / Windows relay）
set -euo pipefail

source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

echo "[T4-Quest] UDP → Quest ${SONIC_QUEST_IP}:17771（头显里 QuestMirror APK 须已打开）"
echo "[T4-Quest] 不需要 unity_udp_relay.ps1，不需要 Quest Link"

cd ~/vr/sonic-bridge
exec python -m sonic_bridge.run_bridge \
  --keyboard-file "${SONIC_QUEST_SAMPLE_FILE}" \
  --udp-host "${SONIC_QUEST_IP}" \
  --hz 60 \
  "$@"
