#!/usr/bin/env bash
# ZIP / fork 安装常缺 Git LFS；josue99999 fork 部分 LFS 404，mesh 从 NVlabs 官方拉。
# 用法: bash /mnt/c/File/vr/scripts/fetch_git_lfs.sh
set -euo pipefail

GROOT="${GROOT:-$HOME/projects/GR00T-WholeBodyControl}"
FORK_URL="${FORK_URL:-https://github.com/josue99999/TELEOPERATION_SONIC.git}"
NVLABS_URL="${NVLABS_URL:-https://github.com/NVlabs/GR00T-WholeBodyControl.git}"
TMP_NV="${TMP_NV:-/tmp/GR00T_nvlabs_lfs}"
TMP_FORK="${TMP_FORK:-/tmp/TELEOPERATION_SONIC_lfs_fetch}"

is_lfs_pointer() {
  local f="$1"
  [[ -f "$f" ]] && head -1 "$f" 2>/dev/null | grep -q 'git-lfs.github.com/spec'
}

mesh_pointer_count() {
  find "$GROOT/gear_sonic/data/robot_model/model_data/g1/meshes" -name '*.STL' 2>/dev/null | while read -r f; do
    is_lfs_pointer "$f" && echo 1
  done | wc -l
}

if [[ ! -d "$GROOT/gear_sonic" ]]; then
  echo "[ERROR] 找不到: $GROOT"
  exit 1
fi

# 损坏的 git init 会导致 'HEAD' ambiguous；ZIP 安装不需要 .git
if [[ -d "$GROOT/.git" ]] && ! git -C "$GROOT" rev-parse HEAD >/dev/null 2>&1; then
  echo "==> 移除损坏的 .git（避免 git HEAD 报错）"
  rm -rf "$GROOT/.git"
fi

bad_meshes=$(mesh_pointer_count)
echo "==> G1 mesh LFS 指针: $bad_meshes 个"
if [[ "$bad_meshes" -eq 0 ]]; then
  echo "[OK] mesh 已就绪"
else
  echo "==> 从 NVlabs 官方仓库拉取 G1 meshes（约 1–3 分钟）"
  rm -rf "$TMP_NV"
  GIT_LFS_SKIP_SMUDGE=1 GIT_HTTP_VERSION=HTTP/1.1 \
    git clone --depth 1 "$NVLABS_URL" "$TMP_NV"
  cd "$TMP_NV"
  git lfs pull --include="gear_sonic/data/robot_model/model_data/g1/meshes/*"
  rsync -a gear_sonic/data/robot_model/model_data/g1/meshes/ \
    "$GROOT/gear_sonic/data/robot_model/model_data/g1/meshes/"
  echo "[OK] mesh 已同步"
  file "$GROOT/gear_sonic/data/robot_model/model_data/g1/meshes/left_hip_pitch_link.STL"
fi

# fork 上可用的 LFS（如 xrobot .so）；失败不阻断
if find "$GROOT/external_dependencies" -name 'libPXREARobotSDK.so' 2>/dev/null | while read -r f; do
  is_lfs_pointer "$f" && exit 0
done; then
  echo "==> 尝试从 fork 拉取 external_dependencies LFS"
  rm -rf "$TMP_FORK"
  GIT_LFS_SKIP_SMUDGE=1 GIT_HTTP_VERSION=HTTP/1.1 \
    git clone --depth 1 "$FORK_URL" "$TMP_FORK" || true
  if [[ -d "$TMP_FORK/.git" ]]; then
    cd "$TMP_FORK"
    git lfs pull --include="external_dependencies/**" || true
    rsync -a external_dependencies/ "$GROOT/external_dependencies/" || true
  fi
fi

bad_after=$(mesh_pointer_count)
if [[ "$bad_after" -gt 0 ]]; then
  echo "[ERROR] 仍有 $bad_after 个 mesh 指针文件"
  exit 1
fi

# deploy 参考动作 CSV（按 ] 后 policy 需要 joint_pos 等）
motion_pointer_count() {
  find "$GROOT/gear_sonic_deploy/reference/example" -name '*.csv' 2>/dev/null | while read -r f; do
    is_lfs_pointer "$f" && echo 1
  done | wc -l
}

bad_motions=$(motion_pointer_count)
echo "==> reference/example CSV LFS 指针: $bad_motions 个"
if [[ "$bad_motions" -gt 0 ]]; then
  echo "==> 从 NVlabs 拉取 reference/example 动作数据（约 1–3 分钟）"
  rm -rf "$TMP_NV"
  GIT_LFS_SKIP_SMUDGE=1 GIT_HTTP_VERSION=HTTP/1.1 \
    git clone --depth 1 "$NVLABS_URL" "$TMP_NV"
  cd "$TMP_NV"
  git lfs pull --include="gear_sonic_deploy/reference/example/**"
  rsync -a gear_sonic_deploy/reference/example/ \
    "$GROOT/gear_sonic_deploy/reference/example/"
  echo "[OK] reference/example 已同步"
  wc -l "$GROOT/gear_sonic_deploy/reference/example/walking_quip_360_R_002__A428/joint_pos.csv" | head -1
fi

bad_motions_after=$(motion_pointer_count)
if [[ "$bad_motions_after" -gt 0 ]]; then
  echo "[ERROR] 仍有 $bad_motions_after 个 reference CSV 指针文件"
  echo "  请手动运行: bash ~/vr/scripts/fetch_git_lfs.sh"
  exit 1
fi

echo "[OK] fetch_git_lfs 完成"
