#!/usr/bin/env bash
# T1 MuJoCo — WSLg 第三人称小窗 + 胸部 FPV 窗口/浏览器
set -euo pipefail

source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate 2>/dev/null \
  || source ~/projects/GR00T-WholeBodyControl/.venv_sim/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

export DISPLAY="${DISPLAY:-:0}"
export MUJOCO_GL="${MUJOCO_GL:-glfw}"
export _GLX_X11_FORCE_MITSHM=0

# WSL2: llvmpipe = 纯 CPU，极慢。D3D12 把 OpenGL 交给 RTX（经 Windows D3D12）。
if [[ "${T1_CPU_GL:-0}" != "1" && -z "${LIBGL_ALWAYS_INDIRECT:-}" ]]; then
  export GALLIUM_DRIVER="${GALLIUM_DRIVER:-d3d12}"
fi

if [[ "${T1_FIX_BLACK:-0}" == "1" ]]; then
  export LIBGL_ALWAYS_INDIRECT=1
  export MESA_GL_VERSION_OVERRIDE="${MESA_GL_VERSION_OVERRIDE:-4.5}"
  echo "[T1] 黑屏修复模式 LIBGL_ALWAYS_INDIRECT=1（若打不开窗请 unset T1_FIX_BLACK）"
else
  unset LIBGL_ALWAYS_INDIRECT
  unset MESA_GL_VERSION_OVERRIDE
fi

if ! command -v glxinfo >/dev/null 2>&1; then
  echo "[T1] 建议: sudo apt install -y mesa-utils libgl1-mesa-dri"
else
  GLX_LINE="$(glxinfo -B 2>/dev/null | grep -E 'OpenGL renderer|direct rendering' | tr '\n' ' ' || true)"
  echo "[T1] glxinfo: ${GLX_LINE:-unknown} (GALLIUM_DRIVER=${GALLIUM_DRIVER:-default})"
fi

echo "[T1] 双视角: ① MuJoCo 第三人称小窗  ② 胸部 FPV 弹窗 + http://127.0.0.1:${SONIC_FPV_PORT:-8765}/"
echo "[T1] GPU: GALLIUM_DRIVER=d3d12 | 减负: T1_LIGHT=1 | 仅网页FPV: T1_NO_FPV_WINDOW=1"
echo "[T1] 倒地/乱态 → Backspace 或 ~/vr/scripts/reset_sonic_session.sh"
echo "[T1] 场景: 厨房台面(默认) | 多任务实验台 → ~/vr/scripts/run_sim_t1_multitask.sh"
echo "[T1] 或 SONIC_SCENE=playground|multitask|empty ~/vr/scripts/run_sim_t1_wsl.sh"

SCENE="${SONIC_SCENE:-playground}"
case "${SCENE,,}" in
  playground|quest_playground|counter) ROBOT_SCENE="playground" ;;
  multitask|quest_multitask|gr00t_lab|gr00t) ROBOT_SCENE="multitask" ;;
  lab|quest_lab) ROBOT_SCENE="lab" ;;
  empty|floor|43dof) ROBOT_SCENE="empty" ;;
  *) ROBOT_SCENE="$SCENE" ;;
esac

cd ~/projects/GR00T-WholeBodyControl

# 每次启动先清旧 T1（避免 8765 占用 / 重复进程）
if pgrep -f "run_sim_loop.py" >/dev/null 2>&1; then
  echo "[T1] 结束旧的 run_sim_loop..."
  pkill -f "run_sim_loop.py" 2>/dev/null || true
  sleep 1
fi

VIEWER_DT="${SONIC_VIEWER_DT:-0.1}"
SIM_HZ="${SONIC_SIM_HZ:-200}"
FPV_PORT="${SONIC_FPV_PORT:-8765}"
FPV_HZ="${SONIC_FPV_HZ:-10}"
SIM_REALTIME="${SONIC_SIM_REALTIME:-1}"

# FPV 默认只绑 127.0.0.1，避免与 Windows portproxy(8765) 冲突（WSL mirrored 网络）
export SONIC_FPV_BIND="${SONIC_FPV_BIND:-127.0.0.1}"

if [[ "${T1_LIGHT:-0}" != "1" ]]; then
  if ss -tlnp "sport = :${FPV_PORT}" 2>/dev/null | grep -q LISTEN \
    || fuser "${FPV_PORT}/tcp" >/dev/null 2>&1; then
    echo "[T1] 端口 ${FPV_PORT} 仍被占用，尝试 fuser -k..."
    fuser -k "${FPV_PORT}/tcp" 2>/dev/null || true
    sleep 1
  fi
fi

FPV_ARGS=(--enable-fpv-stream --fpv-port "$FPV_PORT" --fpv-hz "$FPV_HZ")
if [[ "${T1_LIGHT:-0}" == "1" ]]; then
  FPV_ARGS=()
  FPV_PREVIEW_ARGS=()
fi

RT_ARGS=()
if [[ "$SIM_REALTIME" == "1" ]]; then
  RT_ARGS=(--sim-realtime)
else
  RT_ARGS=(--no-sim-realtime)
fi

FPV_PREVIEW_ARGS=(--enable-fpv-preview)
if [[ "${T1_NO_FPV_WINDOW:-0}" == "1" ]]; then
  FPV_PREVIEW_ARGS=()
fi

echo "[T1] SONIC_SCENE=$SCENE sim=${SIM_HZ}Hz viewer=${VIEWER_DT}s fpv=${FPV_HZ}Hz realtime=$SIM_REALTIME"

exec python gear_sonic/scripts/run_sim_loop.py \
  --sim-frequency "$SIM_HZ" \
  --viewer-dt "$VIEWER_DT" \
  "${RT_ARGS[@]}" \
  --enable-onscreen \
  "${FPV_ARGS[@]}" \
  "${FPV_PREVIEW_ARGS[@]}" \
  --robot-scene "$ROBOT_SCENE" \
  "$@"
