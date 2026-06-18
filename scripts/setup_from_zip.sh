#!/usr/bin/env bash
# 不用 git clone：下载 ZIP 解压到 WSL，再装 sonic-bridge
# 用法: wsl -d Ubuntu bash /mnt/c/File/vr/scripts/setup_from_zip.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 全局 PyPI 镜像（uv + pip），幂等
bash "$SCRIPT_DIR/configure_pypi_mirror.sh"

GROOT="${GROOT:-$HOME/projects/GR00T-WholeBodyControl}"
VR_WIN="/mnt/c/File/vr"
VR_LINK="$HOME/vr"
# codeload 直连比 github.com/archive 少一次重定向，国内 WSL 更稳
ZIP_URL="${ZIP_URL:-https://codeload.github.com/josue99999/TELEOPERATION_SONIC/zip/refs/heads/main}"
BROWSER_ZIP_URL="https://github.com/josue99999/TELEOPERATION_SONIC/archive/refs/heads/main.zip"
TMP_ZIP="/tmp/TELEOPERATION_SONIC.zip"
LOCAL_ZIP="${LOCAL_ZIP:-}"
LOCAL_DIR="${LOCAL_DIR:-/mnt/c/File/sonic/TELEOPERATION_SONIC-main}"
# 常见手动放置位置（按优先级）
LOCAL_ZIP_CANDIDATES=(
  "/mnt/c/File/vr/main.zip"
  "/mnt/c/File/sonic/main.zip"
  "$HOME/Downloads/TELEOPERATION_SONIC-main.zip"
  "$HOME/Downloads/main.zip"
)

find_local_zip() {
  local candidate
  if [[ -n "$LOCAL_ZIP" && -f "$LOCAL_ZIP" ]]; then
    echo "$LOCAL_ZIP"
    return 0
  fi
  for candidate in "${LOCAL_ZIP_CANDIDATES[@]}"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

print_manual_download_help() {
  cat <<EOF

    curl 下载失败（国内访问 GitHub 大文件常见）。
    请改用浏览器下载后重跑脚本，或设置 LOCAL_ZIP / LOCAL_DIR：

      1) 浏览器打开并下载:
         $BROWSER_ZIP_URL

      2) 保存到例如 C:\\File\\vr\\main.zip，然后直接重跑本脚本；或:
         LOCAL_ZIP=/mnt/c/File/vr/main.zip bash $0

      3) 或解压到 C:\\File\\sonic\\TELEOPERATION_SONIC-main\\，然后:
         LOCAL_DIR=/mnt/c/File/sonic/TELEOPERATION_SONIC-main bash $0

    详见: $VR_WIN/docs/COPY_INSTALL.md
EOF
}

download_sonic_zip() {
  local url="$1"
  local dest="$2"
  local curl_args=(
    -L --http1.1
    --connect-timeout 30
    --retry 5 --retry-delay 10
    --progress-bar
    -o "$dest"
  )
  echo "    URL: $url"
  echo "    提示: codeload 不返回文件总大小，进度条可能长时间显示 0；"
  echo "          若 2 分钟内仍无任何字节，请 Ctrl+C 后按上方浏览器方式下载。"
  # 仅 codeload 直连支持 Range；gh-proxy 等镜像用 -C - 会在重试时触发 curl (33)
  if [[ "$url" == "https://codeload.github.com/"* ]]; then
    curl_args=(--retry-all-errors -C - "${curl_args[@]}")
  fi
  rm -f "$dest"
  curl "${curl_args[@]}" "$url"
}

install_from_zip() {
  local zip="$1"
  rm -rf /tmp/TELEOPERATION_SONIC-main
  unzip -q "$zip" -d /tmp
  rm -rf "$GROOT"
  mv /tmp/TELEOPERATION_SONIC-main "$GROOT"
  echo "    解压完成: $GROOT"
}

install_from_dir() {
  local src="$1"
  rm -rf "$GROOT"
  cp -a "$src" "$GROOT"
  echo "    复制完成: $GROOT"
}

echo "==> [1/6] socket buffers"
sudo sysctl -w net.core.rmem_max=2097152 net.core.rmem_default=2097152 \
  net.core.wmem_max=2097152 net.core.wmem_default=2097152 2>/dev/null || true

echo "==> [2/6] apt 依赖"
sudo apt-get update -qq
sudo apt-get install -y unzip curl git git-lfs build-essential python3 python3-pip python3-venv \
  libgl1 libegl1 libx11-6 android-tools-adb android-tools-fastboot

echo "==> [3/6] 下载 SONIC Quest ZIP（约几百 MB，比 git clone 稳）"
mkdir -p "$(dirname "$GROOT")"
if [[ ! -d "$GROOT/gear_sonic" ]]; then
  if local_zip="$(find_local_zip)"; then
    echo "    使用本地 ZIP: $local_zip"
    install_from_zip "$local_zip"
  elif [[ -d "$LOCAL_DIR/gear_sonic" ]]; then
    echo "    使用本地目录: $LOCAL_DIR"
    install_from_dir "$LOCAL_DIR"
  elif download_sonic_zip "$ZIP_URL" "$TMP_ZIP"; then
    install_from_zip "$TMP_ZIP"
    rm -f "$TMP_ZIP"
  else
    print_manual_download_help
    exit 1
  fi
else
  echo "    已存在 $GROOT，跳过下载"
fi

echo "==> [3b/6] Git LFS 大文件（mesh / .so / onnx，ZIP 不含）"
if ! bash "$SCRIPT_DIR/fetch_git_lfs.sh"; then
  echo "    LFS 拉取失败 — 可稍后重跑: bash $SCRIPT_DIR/fetch_git_lfs.sh"
fi

echo "==> [4/6] 链接 Windows 项目到 ~/vr（方便在 WSL 里 cd ~/vr）"
ln -sfn "$VR_WIN" "$VR_LINK"

echo "==> [5/6] 安装 SONIC teleop 环境（install_pico.sh，需 10-30 分钟）"
cd "$GROOT"
if [[ ! -d .venv_teleop ]]; then
  bash install_scripts/install_pico.sh
fi

echo "==> [6/6] 安装 sonic-bridge"
source .venv_teleop/bin/activate
pip install -q -e "$VR_LINK/sonic-bridge"

echo ""
echo "=========================================="
echo "  完成"
echo "  SONIC:  $GROOT"
echo "  本项目: $VR_LINK  (即 C:\\File\\vr)"
echo "=========================================="
echo ""
echo "下一步:"
echo "  source $GROOT/.venv_teleop/bin/activate"
echo "  python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic --duration 5"
echo "  python -m sonic_bridge.standalone_demo"
