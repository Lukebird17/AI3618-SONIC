# ⚠️ 旧版 Unity 工程（已弃用）

**请勿再在此工程上开发。**

| | |
|--|--|
| **旧工程** | `~/vr/quest-mirror-unity/`（本目录） |
| **新工程** | `~/vr/quest-mujoco-vr/quest mujoco vr/` |
| **文档** | `~/vr/docs/COORDINATE_SYSTEMS.md`、`~/vr/docs/UNITY_V2_SETUP.md` |

旧版问题：坐标变换链叠加（Quest room / pelvis / Unity 多次转换）、相机与 SONIC 头部位姿混用、Quest 手柄 overlay 与 MuJoCo 真值不同步。

新工程原则：**场景与双手 100% 来自 MuJoCo `visual_links`；仅相机用 Quest HMD 6DOF（`hmd_view_pose`）。**
