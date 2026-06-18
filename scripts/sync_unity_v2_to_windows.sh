#!/usr/bin/env bash
# Sync Unity v2 project WSL → Windows
set -euo pipefail

VR="${HOME}/vr"
WIN_VR="/mnt/c/File/vr"
INNER="quest mujoco vr"
SRC="${VR}/quest-mujoco-vr/${INNER}"
DST="${WIN_VR}/quest-mujoco-vr/${INNER}"

if [[ ! -d "$SRC" ]]; then
  echo "[sync-v2] Missing: $SRC"
  exit 1
fi

if [[ ! -d "$WIN_VR" ]]; then
  echo "[sync-v2] Windows path not found: $WIN_VR"
  exit 1
fi

mkdir -p "$(dirname "$DST")"
echo "[sync-v2] $SRC → $DST"
rsync -av --delete \
  --exclude 'Library/' \
  --exclude 'Logs/' \
  --exclude 'Temp/' \
  --exclude 'UserSettings/' \
  "$SRC/" "$DST/"

echo "[sync-v2] Open: C:\\File\\vr\\quest-mujoco-vr\\quest mujoco vr"
