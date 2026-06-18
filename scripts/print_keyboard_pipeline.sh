#!/usr/bin/env bash
# Full keyboard pipeline cheat sheet (print only).
set -euo pipefail

cat <<'EOF'
══════════════════════════════════════════════════════════════════
  SONIC + Unity 键盘全链路（4 终端 + Unity Play）
══════════════════════════════════════════════════════════════════

【环境 — 每个 WSL 终端先执行】
  source ~/vr/scripts/wsl_dds_env.sh
  source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
  export PYTHONPATH=~/projects/GR00T-WholeBodyControl

【若 deploy 报 Address already in use :5557】
  bash ~/vr/scripts/kill_sonic_zmq.sh
  然后重新开 T2 deploy

──────────────────────────────────────────────────────────────────
T1 — MuJoCo
  cd ~/projects/GR00T-WholeBodyControl
  python gear_sonic/scripts/run_sim_loop.py

T2 — Deploy（等到 Init done）
  cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy
  source scripts/setup_env.sh
  ./deploy.sh sim --input-type zmq_manager

T3 — Manager + 键盘（★ 焦点必须在此终端 ★）
  cd ~/projects/GR00T-WholeBodyControl
  python gear_sonic/scripts/pico_manager_thread_server.py \
    --manager --reader keyboard --vis_vr3pt

T4 — Bridge → Unity
  cd ~/vr/sonic-bridge
  python -m sonic_bridge.run_bridge \
    --keyboard-file /tmp/sonic_keyboard_sample.json \
    --udp-host 127.0.0.1

Unity: 内层 quest mirror unity → Play

──────────────────────────────────────────────────────────────────
键盘（T3 manager 终端）

  左手 EEF     Q/A X±   W/S Y±   E/D Z±
  右手 EEF     I/K X±   O/L Y±   P/; Z±
  头显         F/J 左右转

  1  启动/停止 policy (等同 Quest A+B+X+Y)
  C  右扳机腕校准
  V  进/出 VR_3PT（左摇杆 Click）
  Y  Unity 显示 CALIBRATION↔TELEOP（bridge HUD）
  X  开始/停止 JSONL 录制
  R  腕位重置    H  帮助

推荐流程:
  1 → 启动 policy
  QWEASD/IOPL; 对准幽灵腕 → C 校准 → V 进 VR_3PT
  动 EEF 看 MuJoCo 跟手 + Unity 镜像
  Y 切 TELEOP 显示层   X 录制

详见: ~/vr/docs/KEYBOARD_TEST.md
EOF
