# 坐标系总览（MuJoCo / Quest / Bridge / Unity v2）

开发新 Unity 前必读。所有软件共用 **一套 MuJoCo/ROS 语义**；只在 **进入 Unity 场景时** 做一次固定变换。

---

## 1. 各软件坐标系

| 软件 | 轴向 | 原点 / 参考 | 备注 |
|------|------|-------------|------|
| **MuJoCo / URDF / Pinocchio FK** | X 前、Y 左、Z 上 | **pelvis**（根 link） | `body_q` → `visual_links` / `robot_actual` 均在 pelvis 帧 |
| **MuJoCo 世界** | 同上 | 地面场景 | `pelvis_world.p = [0, 0, 0.793]`（quest_lab 站立高度） |
| **meta_quest_teleop** | OpenXR 房间系 → **ROS** | Session 原点 = 戴头显时 floor origin | `get_hand_controller_transform_ros()` 已是 ROS，**勿再** `_apply_quest_yz_swap` |
| **SONIC vr_3pt_pose** | ROS pelvis | 行 0/1 腕，行 2 **固定默认头** | deploy 用；**不用 Quest 头追** |
| **Bridge UDP JSON** | ROS pelvis（位置米，四元数 wxyz） | 与 MuJoCo FK 一致 | 发给 Unity 前 **仍是 MuJoCo 帧** |
| **Unity v2 场景** | X 右、Y 上、Z 前 | `WorldRoot` + `RobotRoot` 平移 | 仅在此处 `MujocoFrame.ToUnity()` |

---

## 2. 唯一允许的 Unity 变换

```
p_unity = (-y_m, z_m, x_m)
R_unity = S · R_m · LinkMeshBasis   // 仅 G1 STL mesh；相机/空物体用 PoseOnly（无 LinkMeshBasis）
```

实现：`quest-mujoco-vr/.../MujocoFrame.cs`

**禁止：**
- 在 QuestReader 里为 Unity 再套一层 yz_swap（与 `_ros()` 双重变换）
- 对 `RobotRoot` 施加 pelvis 旋转（只平移 `pelvis_world`）
- 用 Quest room 绝对坐标直接驱动 G1 mesh
- 把 `unity_head_pose` 写进 `vr_3pt.head` 发给 deploy

---

## 3. 数据分工（v2 新协议）

| UDP 字段 | 坐标系 | 用途 |
|----------|--------|------|
| `visual_links.*` | pelvis / ROS | **整机器人 + 双手 mesh**（唯一几何真值） |
| `robot_actual.head` | pelvis / ROS | MuJoCo FK 头部位姿（锚点） |
| `hmd_view_pose` | pelvis / ROS | **操作者相机 6DOF** = FK 头 + Quest HMD session 增量 |
| `vr_3pt` / `vr_3pt_raw` | pelvis / ROS | SONIC 遥操 / 校准 UI（**不驱动 v2 mesh**） |
| `pelvis_world` | 世界 / ROS | 仅平移 `RobotRoot` |
| `unity_head_pose` | — | **旧版** yaw-only；v2 用 `hmd_view_pose` |

### `hmd_view_pose` 算法

```
session 首帧捕获 head_origin（Quest room ROS）
每帧: rel = inv(origin) @ head_current
位置: p = robot_actual.head.p + rel.t
旋转: R = R_fk_head @ (inv(R_calib) @ R_head_current)   // 校准时 R_calib = R_head
```

Quest 仍跑 **meta_quest_teleop**（扳机校准）；Unity 不再显示 Quest 手柄块，只看 MuJoCo 双手。

---

## 4. 旧版 bug 对照

| 现象 | 根因 |
|------|------|
| 天旋地转 | room 坐标当 pelvis；或双重 MuJoCo→Unity |
| 手与幽灵对不上 | room 绝对坐标 vs session 相对增量 |
| 相机飘 | Quest 头位置写相机；应用 FK 头 + HMD 增量 |
| SONIC 头颈异常 | Quest 旋转写入 `vr_3pt.head` |

---

## 5. 变换链图（v2）

```
MuJoCo body_q ──FK──► visual_links / robot_actual ──UDP──► Unity G1 mesh
                              ▲
Quest HMD ──session rel──► hmd_view_pose ──UDP──► Unity Camera（6DOF）
Quest 腕   ──offset───► vr_3pt ──ZMQ──► deploy（与 Unity 显示解耦）
```
