#!/bin/bash
# WSL2: DDS on loopback (lo) does not work — use a real NIC (eth2 on this machine).
# Source in BOTH T1 (run_sim_loop) and T2 (deploy.sh) before starting.

if [[ -z "${SONIC_DDS_INTERFACE:-}" ]]; then
  SONIC_DDS_INTERFACE=$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}')
  if [[ -z "$SONIC_DDS_INTERFACE" ]]; then
    SONIC_DDS_INTERFACE=$(ip -4 addr show 2>/dev/null | awk '/^[0-9]+:/{iface=$2; gsub(/:$/,"",iface)} /inet / && iface!="lo"{print iface; exit}')
  fi
  SONIC_DDS_INTERFACE="${SONIC_DDS_INTERFACE:-eth2}"
elif ! ip -4 addr show "$SONIC_DDS_INTERFACE" 2>/dev/null | grep -q 'inet '; then
  echo "[wsl_dds] Warning: SONIC_DDS_INTERFACE=$SONIC_DDS_INTERFACE 无效，重新检测..." >&2
  unset SONIC_DDS_INTERFACE
  SONIC_DDS_INTERFACE=$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}')
  SONIC_DDS_INTERFACE="${SONIC_DDS_INTERFACE:-eth2}"
fi

SONIC_DDS_IP=$(ip -4 addr show "$SONIC_DDS_INTERFACE" 2>/dev/null | awk '/inet /{print $2; exit}' | cut -d/ -f1 || true)
SONIC_DDS_IP="${SONIC_DDS_IP:-127.0.0.1}"

export SONIC_DDS_INTERFACE
export SONIC_DDS_IP
export DISABLE_CRC_FOR_MUJOCO=1

# Unity Editor on Windows (mirrored WSL2: same LAN IP as eth2)
export SONIC_WIN_IP="${SONIC_WIN_IP:-$SONIC_DDS_IP}"
export SONIC_QUEST_IP="${SONIC_QUEST_IP:-192.168.0.101}"
export SONIC_QUEST_SAMPLE_FILE="${SONIC_QUEST_SAMPLE_FILE:-/tmp/sonic_quest_sample.json}"
export SONIC_TCP_RELAY_PORT="${SONIC_TCP_RELAY_PORT:-17782}"

# C++ deploy (unitree_sdk2) reads CYCLONEDDS_URI — must match Python sim discovery on eth2
export CYCLONEDDS_URI="<?xml version=\"1.0\" encoding=\"UTF-8\" ?><CycloneDDS><Domain><General><Interfaces><NetworkInterface name=\"${SONIC_DDS_INTERFACE}\" multicast=\"default\"/></Interfaces></General><Discovery><ParticipantIndex>auto</ParticipantIndex><Peers><Peer address=\"${SONIC_DDS_IP}\"/></Peers></Discovery></Domain></CycloneDDS>"

echo "SONIC DDS: interface=${SONIC_DDS_INTERFACE} ip=${SONIC_DDS_IP} (WSL MuJoCo sim)"
echo "  Unity (Windows Editor): SONIC_WIN_IP=${SONIC_WIN_IP}  Quest: SONIC_QUEST_IP=${SONIC_QUEST_IP}"
echo "  T1: ~/vr/scripts/run_sim_t1_wsl.sh   # MuJoCo 200Hz + WSLg 小窗 (DISPLAY=:0)"
echo "      黑屏时: docs/QUEST_LINK.md 或 --no-enable-onscreen"
echo "  T2: cd gear_sonic_deploy && ./deploy.sh sim --input-type zmq_manager"
echo "  T4-PC:  ~/vr/scripts/run_bridge_unity_win.sh   # + unity_udp_relay.ps1 (Quest Link / PC Unity)"
echo "  T4-Quest: ~/vr/scripts/run_bridge_quest_apk.sh  # Quest APK in headset, NO Link"
