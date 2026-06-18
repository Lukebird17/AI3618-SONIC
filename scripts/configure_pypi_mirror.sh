#!/usr/bin/env bash
# 配置 WSL 全局 PyPI 镜像（uv + pip），幂等，可重复执行。
# 用法: bash /mnt/c/File/vr/scripts/configure_pypi_mirror.sh
set -euo pipefail

PYPI_MIRROR="${PYPI_MIRROR:-https://pypi.tuna.tsinghua.edu.cn/simple}"
UV_CONCURRENT="${UV_CONCURRENT:-16}"
UV_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/uv"
PIP_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/pip"
UV_CONFIG_FILE="$UV_CONFIG_DIR/uv.toml"
PIP_CONFIG_FILE="$PIP_CONFIG_DIR/pip.conf"
BASHRC="$HOME/.bashrc"
MARKER="# >>> vr pypi mirror >>>"

mkdir -p "$UV_CONFIG_DIR" "$PIP_CONFIG_DIR"

cat > "$UV_CONFIG_FILE" <<EOF
# Managed by /mnt/c/File/vr/scripts/configure_pypi_mirror.sh
# 清华 PyPI 镜像；改 PYPI_MIRROR 后重跑脚本即可切换

[[index]]
url = "$PYPI_MIRROR"
default = true

[pip]
index-url = "$PYPI_MIRROR"
EOF

cat > "$PIP_CONFIG_FILE" <<EOF
# Managed by /mnt/c/File/vr/scripts/configure_pypi_mirror.sh
[global]
index-url = $PYPI_MIRROR
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF

if ! grep -qF "$MARKER" "$BASHRC" 2>/dev/null; then
  cat >> "$BASHRC" <<EOF

$MARKER
export UV_DEFAULT_INDEX="$PYPI_MIRROR"
export UV_INDEX_URL="$PYPI_MIRROR"
export UV_CONCURRENT_DOWNLOADS="$UV_CONCURRENT"
export PIP_INDEX_URL="$PYPI_MIRROR"
export PIP_TRUSTED_HOST="pypi.tuna.tsinghua.edu.cn"
# <<< vr pypi mirror <<<
EOF
fi

echo "[OK] uv 配置:  $UV_CONFIG_FILE"
echo "[OK] pip 配置: $PIP_CONFIG_FILE"
echo "[OK] bashrc 已写入 UV/PIP 环境变量"
echo "     镜像: $PYPI_MIRROR"
echo "     并发: $UV_CONCURRENT"
echo ""
echo "新开终端生效；当前 shell 请执行:"
echo "  source ~/.bashrc"
