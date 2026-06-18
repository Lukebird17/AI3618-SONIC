#!/usr/bin/env bash
# 把 GR00T 里我们改过的文件复制到 vr/patches/gr00t/（保持相对路径）
set -euo pipefail

VR_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GR00T_ROOT="${GR00T_ROOT:-$HOME/projects/GR00T-WholeBodyControl}"
PATCH_ROOT="$VR_ROOT/patches/gr00t/files"

FILES=(
  gear_sonic/utils/teleop/readers/quest_reader.py
  gear_sonic/scripts/pico_manager_thread_server.py
  gear_sonic/utils/mujoco_sim/base_sim.py
  gear_sonic/utils/mujoco_sim/configs.py
  gear_sonic/utils/mujoco_sim/wbc_configs/g1_29dof_sonic_model12.yaml
  gear_sonic/data/robot_model/model_data/g1/scene_quest_playground.xml
  gear_sonic/data/robot_model/model_data/g1/scene_quest_multitask.xml
)

if [[ ! -d "$GR00T_ROOT/gear_sonic" ]]; then
  echo "[export] GR00T 未找到: $GR00T_ROOT" >&2
  echo "  设置: GR00T_ROOT=/path/to/GR00T-WholeBodyControl $0" >&2
  exit 1
fi

mkdir -p "$PATCH_ROOT"
n=0
for rel in "${FILES[@]}"; do
  src="$GR00T_ROOT/$rel"
  dst="$PATCH_ROOT/$rel"
  if [[ ! -f "$src" ]]; then
    echo "[export] 跳过（不存在）: $rel"
    continue
  fi
  mkdir -p "$(dirname "$dst")"
  cp -a "$src" "$dst"
  echo "[export] $rel"
  n=$((n + 1))
done

echo ""
echo "[export] 已导出 $n 个文件 → $PATCH_ROOT"
echo "  git add patches/gr00t && git commit -m 'Update GR00T patches'"
