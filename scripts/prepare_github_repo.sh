#!/usr/bin/env bash
# 在 vr 目录初始化 GitHub 仓库（大文件留原地，靠 .gitignore 排除）
set -euo pipefail

VR_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$VR_ROOT"

echo "=== AI3618 单仓库准备 ==="
echo "目录: $VR_ROOT"
echo ""

# 可选：先导出 GR00T 补丁
if [[ -d "${GR00T_ROOT:-$HOME/projects/GR00T-WholeBodyControl}/gear_sonic" ]]; then
  echo "[1/4] 导出 GR00T 补丁..."
  bash "$VR_ROOT/scripts/export_gr00t_patches.sh" || true
else
  echo "[1/4] 跳过 GR00T 导出（未安装 SONIC）"
fi

echo "[2/4] 检查将被忽略的大文件（仍在磁盘，不会 commit）..."
for pat in "TensorRT-*.tar.gz" "main.zip" "**/Library" "sonic-bridge/recordings/*.jsonl"; do
  found=$(find . -path "./.git" -prune -o -name "${pat##**/}" -print 2>/dev/null | head -1 || true)
  if [[ -n "$found" ]]; then
    echo "  忽略: $pat （示例: $found）"
  fi
done

if [[ ! -d .git ]]; then
  echo "[3/4] git init ..."
  git init
  git branch -M main
else
  echo "[3/4] 已是 git 仓库"
fi

echo "[4/4] git add（受 .gitignore 约束）..."
git add .
echo ""
echo "即将提交的文件数量:"
git status --short | wc -l
echo ""
echo "若列表里出现 TensorRT / Library / 大 jsonl，请检查 .gitignore"
echo ""
git status --short | head -40
if [[ $(git status --short | wc -l) -gt 40 ]]; then
  echo "  ...（更多文件省略）"
fi
echo ""
echo "下一步:"
echo "  1. git commit -m 'Initial commit: AI3618 Quest VR teleop'"
echo "  2. 在 GitHub 新建空仓库 AI3618-Quest-VR-Teleop"
echo "  3. git remote add origin https://github.com/<你>/AI3618-Quest-VR-Teleop.git"
echo "  4. git push -u origin main"
