# Sonic Bridge ↔ Quest Mirror UDP 协议

默认：**UDP JSON**，端口 `17771`（PC → Unity/Quest 广播）

Quest 发送校准/状态（可选）：`17772`（Quest → PC）

---

## 校准 vs 遥操（完整逻辑）

| 操作 | 作用层 | 说明 |
|------|--------|------|
| **右扳机** | SONIC 真校准 | `QuestReader` 写 wrist offset → Manager 才有 `vr_3pt_pose` |
| **Y** | Unity 显示层 | `display_mode`: `CALIBRATION` ↔ `TELEOP`（不写 SONIC offset） |
| **X** | Bridge 录制 | `recording` true/false → JSONL |
| **对准** | 人工 + Align | 物理把手柄摆到 **MuJoCo 幽灵腕**（`g1_ref`）再按右扳机 |

**Unity 里视觉对齐 ≠ SONIC 校准。** 必须右扳机后 bridge 才发 `calibrated=true` 与 `vr_3pt`。

### CALIBRATION 模式（Unity）

| 元素 | UDP 字段 | 含义 |
|------|----------|------|
| 半透明幽灵腕 | `g1_ref` | **MuJoCo FK 同步目标**（`robot_actual` 左右腕，随仿真动） |
| 实心块 | `vr_3pt_raw` | 未校准 Quest 原始腕 pose |
| G1 mesh + 场景 | `visual_links`, `pelvis_world` | 跟 MuJoCo 镜像 |
| Align 分数 | `alignment_score` | **raw 腕 vs `g1_ref`**（不是静态 home） |
| 进 TELEOP 门控 | `safe_to_switch` | `alignment_score >= threshold` 且已右扳机校准 |

流程：**对准幽灵 → Align OK → 右扳机 → 再按 Y → TELEOP**

### TELEOP 模式（Unity）

| 元素 | 字段 | 含义 |
|------|------|------|
| 关幽灵 / 关 raw 块 | `display_mode=TELEOP` | 仅镜像 |
| G1 + 关节 | `visual_links`, `robot_actual` | 纯 MuJoCo 镜像 |
| 指令腕（可选 debug） | `vr_3pt` | 校准后 SONIC 指令 |
| 主视角 | XR HMD 或 `mirror_camera_pose` | Quest 头显解耦；Editor 用 MuJoCo head FK |
| 右下角 PiP | `d435_pose` | 胸载 RealSense D435 视锥（URDF FK） |

---

## PC → Unity：`state` / `ghost` 包（~30 Hz）

```json
{
  "type": "ghost",
  "ts": 1718000000.123,
  "mode": "CALIBRATION",
  "display_mode": "CALIBRATION",
  "calibrated": false,
  "alignment_score": 0.62,
  "safe_to_switch": false,
  "latency_ms": 12.5,
  "recording": false,
  "vr_3pt_raw": {
    "left":  {"p": [0.27, 0.25, 0.45], "q": [1, 0, 0, 0]},
    "right": {"p": [0.27, -0.25, 0.45], "q": [1, 0, 0, 0]},
    "head":  {"p": [0.024, -0.008, 0.403], "q": [0.999, 0.011, 0.04, 0]}
  },
  "g1_ref": {
    "left":  {"p": [0.15, 0.25, 0.45], "q": [1, 0, 0, 0]},
    "right": {"p": [0.15, -0.25, 0.45], "q": [1, 0, 0, 0]}
  },
  "robot_actual": {
    "left":  {"p": [0.15, 0.25, 0.45], "q": [1, 0, 0, 0]},
    "right": {"p": [0.15, -0.25, 0.45], "q": [1, 0, 0, 0]},
    "head":  {"p": [0.024, -0.008, 0.403], "q": [0.999, 0.011, 0.04, 0]},
    "torso": {"p": [0.0, 0.0, 0.9], "q": [1, 0, 0, 0]}
  },
  "camera_pose": {"p": [...], "q": [...]},
  "mirror_camera_pose": {"p": [...], "q": [...]},
  "d435_pose": {"p": [...], "q": [...]},
  "robot_joints": [29 floats],
  "hand_state": {"left_trigger": 0.0, "right_trigger": 0.0, "left_grip": 0.0, "right_grip": 0.0},
  "left_hand_joints": [7],
  "right_hand_joints": [7],
  "visual_links": {"pelvis": {...}, "torso_link": {...}, "...": "..."},
  "pelvis_world": {"p": [0,0,0.793], "q": [1,0,0,0]},
  "scene_name": "quest_lab"
}
```

校准完成后 `type` 可为 `state`，并增加：

```json
"calibrated": true,
"vr_3pt": { "left": {...}, "right": {...}, "head": {...} }
```

### 字段说明

| 字段 | 来源 |
|------|------|
| `g1_ref.left/right` | MuJoCo `robot_actual` 腕（与幽灵腕一致） |
| `vr_3pt_raw` | QuestReader 未校准 raw（始终有） |
| `vr_3pt` | QuestReader 校准后 offset 腕（仅 `calibrated=true`） |
| `mirror_camera_pose` | MuJoCo FK head（Editor 主相机） |
| `hmd_view_pose` | **Unity v2** 相机 6DOF = `robot_actual.head` + Quest HMD session 增量 |
| `d435_pose` | torso + URDF `d435_joint` |
| `visual_links` | 全 link FK（G1Avatar 镜像） |
| `robot_joints` | ZMQ `g1_debug` body_q 或 synthetic |

### Pipeline 按键（bridge）

| 键 | 效果 |
|----|------|
| **Y** | `display_mode` 切换；CALIBRATION→TELEOP 需 `calibrated` + `safe_to_switch` |
| **X** | `recording` 切换；`recording_path` 为 JSONL 路径 |
| **右扳机** | SONIC 腕校准（`quest_calibrated`） |

Editor synthetic 终端：`y` / `x` / `c`（模拟 Y / X / 右扳机）

---

## Path B（MuJoCo 状态同步）

- `robot_joints` ← deploy ZMQ `:5557` 或 `--synthetic`
- `robot_actual`, `visual_links`, `d435_pose`, `mirror_camera_pose` ← 同一套 G1 FK
- `g1_ref` ← 每帧从 `robot_actual` 左右腕同步（幽灵跟仿真）

```bash
# Editor 轻量 demo（无 run_bridge 门控）
python -m sonic_bridge.standalone_demo --udp-host 127.0.0.1

# 完整 pipeline（推荐）
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
python -m sonic_bridge.run_bridge --synthetic --udp-host 127.0.0.1
```

- 四元数 **`[w, x, y, z]`**，位置 **米**，坐标系与 SONIC / MuJoCo 一致
- Unity 转换：`PoseMath.MuJoCoToUnity*`（Z-up → Y-up）

---

## 轨迹文件

`sonic-bridge/recordings/<session_id>.jsonl`：

```json
{
  "display_mode": "TELEOP",
  "recording": true,
  "calibrated": true,
  "alignment_score": 0.95,
  "vr_3pt_pose": [[...],[...],[...]],
  "vr_3pt_raw_pose": [[...],[...],[...]],
  "robot_joints": [...],
  "hand_state": {...}
}
```

回放：`python -m sonic_bridge.mujoco_replay --jsonl recordings/session_xxx.jsonl`

详见 `docs/PIPELINE.md`。
