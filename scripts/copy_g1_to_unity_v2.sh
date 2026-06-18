#!/usr/bin/env bash
# Copy G1 robot meshes + scene Resources from old Unity v1 → v2
set -euo pipefail

OLD="${HOME}/vr/quest-mirror-unity/quest mirror unity/Assets"
NEW="${HOME}/vr/quest-mujoco-vr/quest mujoco vr/Assets"

if [[ ! -d "$OLD/Robot/G1" ]]; then
  echo "[copy-g1] Old G1 not found: $OLD/Robot/G1"
  exit 1
fi

mkdir -p "$NEW/Robot/G1" "$NEW/Resources"
echo "[copy-g1] Robot/G1 ..."
rsync -a --info=progress2 "$OLD/Robot/G1/" "$NEW/Robot/G1/"

if [[ -f "$OLD/Resources/MujocoSceneLayout.json" ]]; then
  echo "[copy-g1] Resources ..."
  rsync -a "$OLD/Resources/MujocoSceneLayout.json" "$OLD/Resources/StandingVisualLinks.json" "$NEW/Resources/" 2>/dev/null || true
fi

echo "[copy-g1] Done. Sync to Windows:"
echo "  ~/vr/scripts/sync_unity_v2_to_windows.sh"
echo "Unity: Sonic MuJoCo VR → 3) Build Scene (Rebuild)"
