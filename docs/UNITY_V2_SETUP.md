# Unity v2 — Sonic MuJoCo VR

## 开哪个工程

| 版本 | 路径 | 状态 |
|------|------|------|
| **v2（新）** | `~/vr/quest-mujoco-vr/quest mujoco vr` | 开发中 |
| **v1（旧）** | `~/vr/quest-mirror-unity/quest mirror unity` | 已弃用，见 `DEPRECATED_OLD.md` |

## 一次性

1. Unity Hub 打开 v2 工程
2. 菜单 **Sonic MuJoCo VR → 2) Copy G1 Meshes From Old Project**（或从旧工程复制 `Assets/Robot/G1`）
3. **Sonic MuJoCo VR → 1) Build Scene (v2)**
4. **Quest APK / Link（可选，以后再做）**：需要 OpenXR 时用 **Tuanjie 专用包**，与旧工程一致：
   ```json
   "com.unity.xr.management": "4.5.1",
   "com.unity.xr.openxr": "1.14.4-t2"
   ```
   不要用 npm 上的 `1.9.1`（会在 2022.3.62t9 上报 `OpenXRDevice.cs` CS0019）。
   v2 默认 **不含 XR 包**——PC Play + UDP `hmd_view_pose` 即可联调。

## 每次演示

```bash
# T1 MuJoCo
~/vr/scripts/run_sim_t1_wsl.sh

# T2
source ~/vr/scripts/wsl_dds_env.sh
cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy
./deploy.sh sim --input-type zmq_manager

# T3 — Quest 前台 meta_quest_teleop（扳机校准）
python gear_sonic/scripts/pico_manager_thread_server.py \
  --manager --reader quest --quest-ip-address <QUEST_IP>

# T4 — bridge → Unity
~/vr/scripts/run_bridge_unity_win.sh
```

Unity Play（PC）或 Quest Mirror APK 收 UDP 17771。

## 操作说明

- **看**：Unity 里 MuJoCo 环境 + `hmd_view_pose` 相机
- **手**：画面里全是 MuJoCo FK，与仿真对齐
- **校准/遥操**：Quest 上 **teleop APK** 右扳机 + Manager 按键（与 SONIC 相同）
- **不要**在遥操时切 Quest Browser（会挤掉 teleop）

## 同步 WSL → Windows

```bash
~/vr/scripts/sync_unity_v2_to_windows.sh
```

## 相关文档

- `COORDINATE_SYSTEMS.md` — 坐标系
- `PROTOCOL.md` — UDP 字段（含 `hmd_view_pose`）
- `MUJOCO_FPV_QUEST.md` — 不用 Unity 时的 Browser FPV 备选
