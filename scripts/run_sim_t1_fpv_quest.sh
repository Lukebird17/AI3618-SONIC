#!/usr/bin/env bash
# T1 MuJoCo + head FPV MJPEG for Quest Browser (no Unity).
set -euo pipefail

source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate 2>/dev/null \
  || source ~/projects/GR00T-WholeBodyControl/.venv_sim/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

export DISPLAY="${DISPLAY:-:0}"
export MUJOCO_GL="${MUJOCO_GL:-egl}"
export _GLX_X11_FORCE_MITSHM=0

FPV_PORT=8765
if ss -tlnp "sport = :${FPV_PORT}" 2>/dev/null | grep -q LISTEN; then
  echo "[T1+FPV] 端口 ${FPV_PORT} 已被占用，正在结束旧的 run_sim_loop..."
  pkill -f "run_sim_loop.py.*--fpv-port ${FPV_PORT}" 2>/dev/null || true
  sleep 1
  if ss -tlnp "sport = :${FPV_PORT}" 2>/dev/null | grep -q LISTEN; then
    echo "[T1+FPV] 仍无法释放 ${FPV_PORT}。请手动: ss -tlnp | grep ${FPV_PORT}" >&2
    exit 1
  fi
fi

# hostname -I 可能先列出 Tailscale；Quest 需与 WSL 同网段 IP（wsl_dds_env 已解析）
LAN_IP="${SONIC_DDS_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
WIN_WIFI_IP="$(powershell.exe -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { \$_.InterfaceAlias -match 'WLAN|Wi-Fi|WiFi' -and \$_.IPAddress -notlike '169.*' } | Select-Object -First 1 -ExpandProperty IPAddress)" 2>/dev/null | tr -d '\r\n')"
echo "[T1+FPV] PC 浏览器 → http://localhost:${FPV_PORT}/  （本机请用 localhost，不要用 ${LAN_IP}）"
if [[ -n "${WIN_WIFI_IP}" ]]; then
  echo "[T1+FPV] Quest 浏览器 → http://${WIN_WIFI_IP}:${FPV_PORT}/  （需先运行 setup_fpv_quest_network.ps1）"
fi
echo "[T1+FPV] Quest/PC 用 192.168.x.x 打不开时：Windows 管理员 PowerShell 运行 setup_fpv_quest_network.ps1"
echo "[T1+FPV] 头显里打开浏览器，输入上面地址，双击画面全屏"
echo "[T1+FPV] 这是 MuJoCo 真渲染像素（单目），不是 Unity 重建"

cd ~/projects/GR00T-WholeBodyControl
exec python gear_sonic/scripts/run_sim_loop.py \
  --sim-frequency 200 \
  --viewer-dt 0.05 \
  --no-enable-onscreen \
  --enable-fpv-stream \
  --fpv-port "${FPV_PORT}" \
  --fpv-hz 30 \
  "$@"
