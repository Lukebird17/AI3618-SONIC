#!/usr/bin/env bash
# Sync OLD Unity project (v1). For v2 use sync_unity_v2_to_windows.sh
set -euo pipefail
echo "[sync] NOTE: v1 deprecated — v2: ~/vr/scripts/sync_unity_v2_to_windows.sh" >&2

VR="${HOME}/vr"
WIN_VR="/mnt/c/File/vr"

if [[ ! -d "$WIN_VR" ]]; then
  echo "[sync] Windows path not found: $WIN_VR"
  echo "[sync] If your Windows vr folder is elsewhere, rsync manually:"
  echo "  rsync -av ~/vr/quest-mirror-unity/ '/mnt/c/YourPath/vr/quest-mirror-unity/'"
  exit 1
fi

INNER="quest mirror unity"
SRC="${VR}/quest-mirror-unity/${INNER}"
DST="${WIN_VR}/quest-mirror-unity/${INNER}"

if [[ ! -d "$SRC" ]]; then
  echo "[sync] Missing source: $SRC"
  exit 1
fi

echo "[sync] WSL → Windows"
echo "  $SRC"
echo "  → $DST"

rsync -av --delete \
  --exclude 'Library/' \
  --exclude 'Logs/' \
  --exclude 'Temp/' \
  --exclude 'UserSettings/' \
  --exclude '.codely-cli/' \
  "$SRC/" "$DST/"

# Also refresh outer Assets (legacy) from canonical inner Assets
rsync -av "${SRC}/Assets/" "${WIN_VR}/quest-mirror-unity/Assets/"
rsync -av "${SRC}/Assets/" "${VR}/quest-mirror/Assets/"

echo "[sync] Done. Open Unity project:"
echo "  C:\\File\\vr\\quest-mirror-unity\\quest mirror unity"
