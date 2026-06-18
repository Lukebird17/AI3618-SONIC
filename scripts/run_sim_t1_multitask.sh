#!/usr/bin/env bash
# T1 MuJoCo — 多任务实验台场景（GR00T locomanip 风格）
# 与厨房台面 playground 分开启动，T3 遥操流程不变。
set -euo pipefail

export SONIC_SCENE=multitask

echo "[T1] 多任务实验台 — 7 项小任务（见终端 [Task] 提示）"
echo "[T1] 物体布局: 左=红圆柱+白盘+绿盒 | 中=绿瓶 | 右=蓝方块+蓝盒 | 后=水龙头"
echo "[T1] 回到厨房台面: ~/vr/scripts/run_sim_t1_wsl.sh"

exec ~/vr/scripts/run_sim_t1_wsl.sh "$@"
