#!/usr/bin/env bash
# T4: T3 sample JSON → bridge → TCP relay → Windows Unity Editor (Play)
# Quest 只由 T3 manager 连接；T4 读 /tmp/sonic_quest_sample.json，避免抢 adb。
set -euo pipefail

source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

cd ~/vr/sonic-bridge
exec python -m sonic_bridge.run_bridge \
  --keyboard-file "${SONIC_QUEST_SAMPLE_FILE}" \
  --udp-host "${SONIC_WIN_IP}" \
  --tcp-relay-port "${SONIC_TCP_RELAY_PORT}" \
  --hz 60 \
  "$@"
