#!/usr/bin/env bash
# 补全 gear_sonic_deploy 的 unitree_sdk2 Git LFS 二进制（ZIP 安装常见缺失）
# 用法:
#   bash /mnt/c/File/vr/scripts/fetch_unitree_lfs.sh
#   MANUAL_DIR=/mnt/c/Users/你/Downloads bash ...
set -euo pipefail

GROOT="${GROOT:-$HOME/projects/GR00T-WholeBodyControl}"
BASE="$GROOT/gear_sonic_deploy/thirdparty/unitree_sdk2"
MANUAL_DIR="${MANUAL_DIR:-/mnt/c/File/vr/unitree_lfs}"

# x86_64 仿真编译必需（WSL + deploy）
FILES=(
  "lib/x86_64/libunitree_sdk2.a|27351696"
  "thirdparty/lib/x86_64/libddsc.so|7493272"
  "thirdparty/lib/x86_64/libddscxx.so|3108976"
)

MEDIA_BASE="https://media.githubusercontent.com/media/NVlabs/GR00T-WholeBodyControl/main/gear_sonic_deploy/thirdparty/unitree_sdk2"

is_lfs_pointer() {
  local f="$1"
  [[ -f "$f" ]] && head -1 "$f" 2>/dev/null | grep -q 'git-lfs.github.com/spec'
}

size_ok() {
  local f="$1" expect="$2"
  [[ -f "$f" ]] || return 1
  is_lfs_pointer "$f" && return 1
  local got
  got=$(wc -c < "$f" | tr -d ' ')
  # 允许 ±1% 误差
  local min=$((expect * 99 / 100))
  local max=$((expect * 101 / 100))
  [[ "$got" -ge "$min" && "$got" -le "$max" ]]
}

try_copy_manual() {
  local rel="$1" dest="$2"
  local name base
  name=$(basename "$rel")
  for base in "$MANUAL_DIR" "/mnt/c/File/vr" "$HOME/Downloads"; do
    [[ -d "$base" ]] || continue
    if [[ -f "$base/$name" ]]; then
      cp -f "$base/$name" "$dest"
      return 0
    fi
    if [[ -f "$base/$rel" ]]; then
      cp -f "$base/$rel" "$dest"
      return 0
    fi
  done
  return 1
}

download_curl() {
  local url="$1" dest="$2"
  echo "   curl: $url"
  curl -fL --http1.1 --retry 3 --connect-timeout 30 --speed-time 120 --speed-limit 1024 \
    -o "$dest.part" "$url" && mv "$dest.part" "$dest"
}

download_powershell() {
  local url="$1" dest="$2"
  local win_dest
  win_dest=$(wslpath -w "$dest")
  echo "   PowerShell 下载（走 Windows 网络，通常比 WSL curl 快）..."
  powershell.exe -NoProfile -Command "
    \$ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri '$url' -OutFile '$win_dest' -TimeoutSec 3600
  "
}

install_one() {
  local rel="$1" expect="$2"
  local dest="$BASE/$rel"
  local url="$MEDIA_BASE/$rel"
  mkdir -p "$(dirname "$dest")"

  if size_ok "$dest" "$expect"; then
    echo "[OK] $rel ($(wc -c < "$dest" | tr -d ' ') bytes)"
    return 0
  fi

  echo "==> 需要: $rel (约 $((expect / 1024 / 1024)) MB)"

  if try_copy_manual "$rel" "$dest" && size_ok "$dest" "$expect"; then
    echo "   已从手动目录复制"
    return 0
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    if download_powershell "$url" "$dest" && size_ok "$dest" "$expect"; then
      return 0
    fi
    rm -f "$dest"
  fi

  if download_curl "$url" "$dest" && size_ok "$dest" "$expect"; then
    return 0
  fi
  rm -f "$dest" "$dest.part" 2>/dev/null || true
  return 1
}

if [[ ! -d "$BASE" ]]; then
  echo "[ERROR] 找不到 $BASE"
  exit 1
fi

echo "==> unitree_sdk2 LFS 修复"
echo "    目标: $BASE"
echo "    手动放置目录: $MANUAL_DIR"
echo ""

failed=0
for entry in "${FILES[@]}"; do
  rel="${entry%%|*}"
  expect="${entry##*|}"
  if ! install_one "$rel" "$expect"; then
    failed=1
    echo "[FAIL] $rel"
  fi
done

if [[ "$failed" -ne 0 ]]; then
  cat <<EOF

❌ 自动下载失败（WSL 访问 GitHub 常很慢）。

【推荐】用 Windows 浏览器下载下面 3 个文件，放到:
  C:\\File\\vr\\unitree_lfs\\

1) libunitree_sdk2.a (~26 MB)
   $MEDIA_BASE/lib/x86_64/libunitree_sdk2.a

2) libddsc.so (~7.1 MB)
   $MEDIA_BASE/thirdparty/lib/x86_64/libddsc.so

3) libddscxx.so (~3.0 MB)
   $MEDIA_BASE/thirdparty/lib/x86_64/libddscxx.so

放好后重新运行:
  bash /mnt/c/File/vr/scripts/fetch_unitree_lfs.sh

校验:
  file $BASE/lib/x86_64/libunitree_sdk2.a   # 应显示 current ar archive
  ls -la $BASE/lib/x86_64/libunitree_sdk2.a # 约 27351696 字节

然后:
  cd $GROOT/gear_sonic_deploy && just build
EOF
  exit 1
fi

echo ""
echo "[OK] unitree_sdk2 LFS 已就绪，可重新 just build"
