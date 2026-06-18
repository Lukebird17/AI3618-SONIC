# Sonic MuJoCo VR v2

MuJoCo 真值镜像 + Quest HMD 视角。旧 Unity 见 `~/vr/quest-mirror-unity/DEPRECATED_OLD.md`。

## 原则

| 来源 | 驱动什么 |
|------|----------|
| `visual_links` | 整场景 G1（含双手）— 与 MuJoCo 完全一致 |
| `hmd_view_pose` | 相机 6DOF（Quest 头显相对 session 增量 + MuJoCo 头 FK 锚点） |
| `vr_3pt` | 仅 SONIC deploy；**不**驱动 Unity mesh |

坐标系：`~/vr/docs/COORDINATE_SYSTEMS.md`

## 打开工程

```
Windows: C:\File\vr\quest-mujoco-vr\quest mujoco vr
WSL:     ~/vr/quest-mujoco-vr/quest mujoco vr
```

Unity Hub → Add → 选上述文件夹（含 `Assets/`、`Packages/`）。

菜单：**Sonic MuJoCo VR → 1) Build Scene (v2)**

若缺 G1 mesh：**2) Copy G1 Meshes From Old Project**

## 运行

```bash
# T1 T2 T3 同 MUJOCO_FPV_QUEST.md
~/vr/scripts/run_bridge_unity_win.sh   # 或 run_bridge_quest_apk.sh
```

Bridge 需发 `hmd_view_pose`（已更新 sonic-bridge + quest_reader）。

## 与旧版区别

- 无 Quest 手柄 overlay / 幽灵块（校准仍用 teleop APK 右扳机）
- 单一 `MujocoFrame` 变换，无 `OperatorCameraRig` yaw-only 混用
- 相机跟 HMD 全 6DOF，身体跟 MuJoCo
