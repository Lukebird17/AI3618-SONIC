# SONIC Quest Mirror — 完整 Pipeline

校准 → 工作遥操 → 数据采集 → MuJoCo 回放

## 按键映射（Quest 手柄）

| 按键 | 作用 | 说明 |
|------|------|------|
| **右扳机** | 腕部校准（**仅首次**；重校：Menu+右扳机） | SONIC 官方 `QuestReader` |
| **X** | 启动/停止 **policy**（T3） | 不再用于 Unity 录制 |
| **左摇杆 Click** | 进入/退出 **VR_3PT** | Unity 自动切 **TELEOP** |
| **Y** | Unity 手动切换（仅无 T3 时） | 有 T3 时随 VR_3PT 自动 |
| **左握把+Y** | T4 **JSONL 录制** | 避免与 T3 的 X 冲突 |
| **扳机 / 握把** | G1 灵巧手 | 官方 manager：`trigger>0.5` → 中指握合 → gripper IK → deploy |

> deploy 进入 `VR_3PT` 仍用官方流程（manager + 左摇杆 Click 等）。Y/X 是 **quest-mirror 创新层**。

## 灵巧手原理（官方 SONIC，Quest 与 PICO 相同）

```
Quest trigger/grip
  → pico_manager generate_finger_data (25×4×4 指尖目标)
  → G1GripperIKSolver
  → left/right_hand_joints (7-DOF)
  → ZMQ pose → deploy → MuJoCo 仿真手
```

bridge 在 UDP 包里附带 `hand_state` 和 IK 后的关节，供 Unity HUD 显示；**实际控制 deploy 的仍是 T3 manager**。

## 终端布局（有 Quest + 真机仿真）

```bash
# 每次新 shell
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

# T1 仿真
python gear_sonic/scripts/run_sim_loop.py --interface eth2

# T2 deploy
cd gear_sonic_deploy && ./deploy.sh eth2 --input-type zmq_manager

# T3 manager（Quest 读手柄 + 手 IK + ZMQ 发 deploy）
python gear_sonic/scripts/pico_manager_thread_server.py \
  --manager --reader quest --quest-ip <QUEST_IP>

# T4 bridge（MuJoCo FK → Unity + 录制）
# T3 独占 Quest；T4 读 sample 文件 + TCP relay 到 Windows Unity（不要用 --quest-ip）
source ~/vr/scripts/wsl_dds_env.sh
cd ~/vr/sonic-bridge
~/vr/scripts/run_bridge_unity_win.sh
# Windows 另开: unity_udp_relay.ps1
```

Unity：**内层** `quest mirror unity` → **Build Everything (Complete)** → Play

## Editor 无 Quest 测试

**推荐 — 键盘遥操（完整校准/遥操/录制流程）：**

```bash
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
cd ~/vr/sonic-bridge
python -m sonic_bridge.run_bridge --keyboard --udp-host 127.0.0.1
```

详见 [`KEYBOARD_TEST.md`](KEYBOARD_TEST.md)（含环境、Unity、可选 MuJoCo T1/T2）。

轻量 UDP 流（无 Y/X/校准门控）：

```bash
python -m sonic_bridge.standalone_demo --udp-host 127.0.0.1
```

旧 synthetic 自动摆腕（需回车）：

```bash
python -m sonic_bridge.run_bridge --synthetic --udp-host 127.0.0.1
```

## 数据采集

- 按 **X** 开始/停止；文件在 `~/vr/sonic-bridge/recordings/session_YYYYMMDD_HHMMSS.jsonl`
- 每行含：`vr_3pt_pose`, `hand_state`, `left/right_hand_joints`, `robot_joints`, `display_mode`

## MuJoCo 回放

```bash
# 回放 bridge JSONL → ZMQ（需 T1+T2 已跑且 deploy 在 VR_3PT）
python -m sonic_bridge.mujoco_replay --jsonl recordings/session_xxx.jsonl

# 回放官方 manager NPZ（完整 SMPL， fidelity 最高）
python -m sonic_bridge.mujoco_replay --npz-dir /path/to/manager/record_dir

# 同时回放给 Unity
python -m sonic_bridge.mujoco_replay --jsonl recordings/session_xxx.jsonl --target both \
  --udp-host $WIN_IP
```

## 与官方采集的关系

- 官方：`左 grip + A/B` 在 manager 内 toggle（写 NPZ 到 `--record-dir`）
- 创新：bridge **X 键** 写 JSONL（轻量，含 vr_3pt + 手 + MuJoCo joints）
- 高精度回放优先用 **manager NPZ**；演示/大作业流程用 **JSONL + mujoco_replay**
