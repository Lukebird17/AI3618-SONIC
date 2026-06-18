# SONIC Quest 代码阅读笔记

基于 [PR #65](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/65) 与 `quest_reader.py`。

## 数据流

```
meta_quest_teleop APK (Quest)
  → MetaQuestReader (Python, USB/WiFi)
  → QuestReader._run_meta_quest()
  → sample["vr_3pt_pose"]  shape (3, 7)
  → pico_manager_thread_server.py (--reader quest)
  → ZMQ PUB → gear_sonic_deploy (C++)
  → MuJoCo G1 仿真
```

## VR 3-Point 格式

`vr_3pt_pose`: `(3, 7)` float32，机器人坐标系 **X=前 Y=左 Z=上**（ROS）

| Row | 含义 | 列 |
|-----|------|-----|
| 0 | 左腕 L-Wrist | `[x, y, z, qw, qx, qy, qz]` |
| 1 | 右腕 R-Wrist | 同上 |
| 2 | 头 Head | Quest 无头追时用固定默认 `VR_3PT_HEAD_*` |

## 校准逻辑（QuestReader）

1. Manager 启动时用 G1 FK 默认腕 pose 作为 `home_left_pose` / `home_right_pose`
2. 操作者摆 G1 默认 pose → **右扳机** rising edge
3. `left_offset = home_left @ inv(left_raw)`（右同理）
4. 之后：`left_pose = left_offset @ left_raw`

与我们的 Unity 幽灵校准 **同一思路**，可在 bridge 里算 **alignment score**。

## Manager 模式（`pico_manager_thread_server.py`）

| 按键 | 作用 |
|------|------|
| A+B+X+Y | 启动 policy / 全量校准 |
| A+X | POSE ↔ PLANNER 切换 |
| 左摇杆 Click | PLANNER ↔ VR_3PT |
| 右摇杆 | 转向 facing |
| 左摇杆 | locomotion |
| Menu 按住 | 暂停 pose 流 |

Quest 模式下按键从 `sample["button_*"]` 读取，不再依赖 PICO XRoboToolkit。

## 我们的 bridge 接入点（Path B — MuJoCo FPV）

**数据流（已实现）：**

```
MuJoCo sim → deploy ZMQ g1_debug (body_q_measured)
  → sonic-bridge (G1 FK → robot_actual + camera_pose)
  → UDP 17771 → Quest Unity FPV + 误差箭头

Quest vr_3pt → bridge (alignment_score) → 同上 UDP
```

Unity 组件：`FpvCameraController`, `ActualWristView`, `CommandWristView`, `WristErrorArrowView`, `MujocoBodyRigView`

Editor 测试：`Sonic Quest Mirror > Setup Scene (Path B)` + `python -m sonic_bridge.standalone_demo`

## 头显显示（官方）

- Quest 上只有 **meta_quest_teleop 小 APK**，**不显示 G1**
- G1 在 **PC MuJoCo 窗口**
- PC 端可选 `--vis_vr3pt` PyVista 3D 调试
- **我们的 Unity App** 补 Quest 内可视化（创新点）

## 推荐 clone 源

PR 未 merge 前可用：

```bash
git clone https://github.com/josue99999/TELEOPERATION_SONIC.git ~/projects/GR00T-WholeBodyControl
```

或 NVlabs main + fetch PR #65 branch `feature/meta-quest3-support`。
