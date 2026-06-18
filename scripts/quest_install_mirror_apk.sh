#!/usr/bin/env bash
# 安装 QuestMirror.apk 到头显（USB 或 WiFi adb）
set -euo pipefail

source ~/vr/scripts/wsl_dds_env.sh

APK_WSL="$HOME/vr/quest-mirror-unity/quest mirror unity/Builds/QuestMirror.apk"
APK_WIN="/mnt/c/File/vr/quest-mirror-unity/quest mirror unity/Builds/QuestMirror.apk"

if [[ -f "$APK_WSL" ]]; then
  APK="$APK_WSL"
elif [[ -f "$APK_WIN" ]]; then
  APK="$APK_WIN"
else
  echo "找不到 APK。先在 Unity：Sonic Quest Mirror → 4) Build Quest APK"
  exit 1
fi

if ! adb devices | grep -qE 'device$'; then
  echo "adb 无设备，尝试 WiFi: adb connect ${SONIC_QUEST_IP}:5555"
  adb connect "${SONIC_QUEST_IP}:5555" || true
  sleep 1
fi

adb devices
adb install -r "$APK"
echo "安装完成。头显 应用库 → quest mirror unity → 打开后再跑 T4-Quest"
