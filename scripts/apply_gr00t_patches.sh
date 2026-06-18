#!/usr/bin/env bash
# 将 vr/patches/gr00t/files/ 覆盖到 GR00T 安装目录
set -euo pipefail

VR_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GR00T_ROOT="${GR00T_ROOT:-$HOME/projects/GR00T-WholeBodyControl}"
PATCH_ROOT="$VR_ROOT/patches/gr00t/files"

if [[ ! -d "$PATCH_ROOT" ]]; then
  echo "[patch] 无补丁目录: $PATCH_ROOT" >&2
  echo "  维护者先运行: ~/vr/scripts/export_gr00t_patches.sh" >&2
  exit 1
fi

if [[ ! -d "$GR00T_ROOT/gear_sonic" ]]; then
  echo "[patch] GR00T 未找到: $GR00T_ROOT" >&2
  exit 1
fi

n=0
while IFS= read -r -d '' f; do
  rel="${f#"$PATCH_ROOT"/}"
  dst="$GR00T_ROOT/$rel"
  mkdir -p "$(dirname "$dst")"
  cp -a "$f" "$dst"
  echo "[patch] → $rel"
  n=$((n + 1))
done < <(find "$PATCH_ROOT" -type f -print0)

echo ""
echo "[patch] 已应用 $n 个文件到 $GR00T_ROOT"
