#!/usr/bin/env bash
# 全场复位：T1 默认站姿+弹力绳 ON；T3 清校准+停 policy
set -euo pipefail

touch /tmp/sonic_mujoco_session_reset
touch /tmp/sonic_manager_session_reset
rm -f /tmp/sonic_mujoco_release_band

echo "[reset] 已发 reset 信号"
echo "  T1: MuJoCo 默认 pose + 弹力绳（或 MuJoCo 小窗按 Backspace）"
echo "  T3: policy OFF + 清校准"
echo "  重新控制: 对准 G1 默认 pose → Quest 按 B 校准 → 按 Y 放绳+ONNX 遥操"
echo "  左摇杆前后走 | 右摇杆左右转身体 | 扳机/握把=手指"
echo ""
echo "  A = 全场复位（机器人+物件）| 完成任务不会自动复位"
echo "  场景布局: 左盘 | 中苹果 | 右方块 | 后方水龙头"
echo "  （Quest 上也可直接按 A 复位，效果相同）"
