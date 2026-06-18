#!/usr/bin/env bash
# 安装 TensorRT（gear_sonic_deploy 编译必需）
# 用法:
#   bash /mnt/c/File/vr/scripts/install_tensorrt.sh /path/to/TensorRT-10.13.*.tar.gz
#   TENSORRT_TAR=/mnt/c/Users/你/Downloads/TensorRT-*.tar.gz bash ...
set -euo pipefail

INSTALL_ROOT="${INSTALL_ROOT:-$HOME/TensorRT}"
TENSORRT_TAR="${TENSORRT_TAR:-${1:-}}"

TAR_CANDIDATES=(
  "$TENSORRT_TAR"
  "/mnt/c/File/vr/TensorRT-10.13"*.tar.gz
  "/mnt/c/File/sonic/TensorRT-10.13"*.tar.gz
  "$HOME/Downloads/TensorRT-10.13"*.tar.gz
  "/mnt/c/Users/*/Downloads/TensorRT-10.13"*.tar.gz
)

find_tar() {
  local pattern path
  for pattern in "${TAR_CANDIDATES[@]}"; do
    [[ -z "$pattern" ]] && continue
    for path in $pattern; do
      if [[ -f "$path" ]]; then
        echo "$path"
        return 0
      fi
    done
  done
  return 1
}

ensure_bashrc_line() {
  local key="$1"
  local line="$2"
  if grep -qF "$key" "$HOME/.bashrc" 2>/dev/null; then
    return 0
  fi
  {
    echo ""
    echo "# TensorRT (gear_sonic_deploy)"
    echo "$line"
  } >> "$HOME/.bashrc"
}

if [[ -d "$INSTALL_ROOT/include" && -f "$INSTALL_ROOT/include/NvInfer.h" ]]; then
  echo "✅ TensorRT 已存在于 $INSTALL_ROOT"
else
  TAR_PATH=""
  if TAR_PATH="$(find_tar)"; then
    :
  else
    cat <<'EOF'
❌ 未找到 TensorRT tar 包。

请从 NVIDIA 下载（需登录开发者账号）:
  https://developer.nvidia.com/tensorrt/download/10x

桌面 x86_64 + CUDA 12.x 选:
  TensorRT 10.13.x — Linux x86_64 — TAR — cuda-12.x  (~10 GB)

下载后任选其一:
  1) 放到 /mnt/c/File/vr/TensorRT-10.13.x.Linux.x86_64-gnu.cuda-12.x.tar.gz
  2) 传参: bash install_tensorrt.sh /path/to/TensorRT-*.tar.gz
  3) 环境变量: TENSORRT_TAR=/path/to/... bash install_tensorrt.sh
EOF
    exit 1
  fi

  echo "📦 使用压缩包: $TAR_PATH"
  WORK_DIR="$(mktemp -d)"
  trap 'rm -rf "$WORK_DIR"' EXIT

  echo "⏳ 解压中（约 10 GB，请耐心等待）..."
  tar -xzf "$TAR_PATH" -C "$WORK_DIR"

  EXTRACTED="$(find "$WORK_DIR" -maxdepth 1 -type d -name 'TensorRT-*' | head -1)"
  if [[ -z "$EXTRACTED" || ! -f "$EXTRACTED/include/NvInfer.h" ]]; then
    echo "❌ 解压后未找到 include/NvInfer.h，请确认下载的是 Linux x86_64 TAR 包"
    exit 1
  fi

  rm -rf "$INSTALL_ROOT"
  mv "$EXTRACTED" "$INSTALL_ROOT"
  echo "✅ 已安装到 $INSTALL_ROOT"
fi

export TensorRT_ROOT="$INSTALL_ROOT"
export LD_LIBRARY_PATH="$TensorRT_ROOT/lib:${LD_LIBRARY_PATH:-}"

ensure_bashrc_line 'export TensorRT_ROOT=' "export TensorRT_ROOT=\"$INSTALL_ROOT\""
ensure_bashrc_line 'TensorRT_ROOT/lib' 'export LD_LIBRARY_PATH="$TensorRT_ROOT/lib:$LD_LIBRARY_PATH"'

echo ""
echo "🔍 校验:"
echo "   TensorRT_ROOT=$TensorRT_ROOT"
echo "   NvInfer.h: $TensorRT_ROOT/include/NvInfer.h"
if [[ -f "$TensorRT_ROOT/include/NvInferVersion.h" ]]; then
  grep -E 'NV_TENSORRT_(MAJOR|MINOR|PATCH)' "$TensorRT_ROOT/include/NvInferVersion.h" | head -3
fi

echo ""
echo "下一步（新终端或 source ~/.bashrc 后）:"
echo "  cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy"
echo "  source scripts/setup_env.sh"
echo "  just build"
echo "  ./deploy.sh sim --input-type keyboard   # 无 Quest 时先用键盘验证"
