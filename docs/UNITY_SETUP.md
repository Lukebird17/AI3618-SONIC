# Unity 完整版 Setup（必读）

## 你看到的菜单不对？先对一下工程

| 你看到的菜单 | 说明你开错了工程 |
|-------------|------------------|
| `Setup Scene (Editor UDP Test)` | **旧工程 / 外层 / quest-mirror 脚本副本** |
| `Build Everything (Complete — Meshes + Scene)` | **正确 — 完整版** |

### 必须打开这个文件夹（内层）

**Windows:** `C:\File\vr\quest-mirror-unity\quest mirror unity`

**WSL:** `~/vr/quest-mirror-unity/quest mirror unity`

不要开：
- `C:\File\vr\quest-mirror-unity`（外层，只有 Assets 副本）
- `C:\File\vr\quest-mirror`（只有脚本，不是完整 Unity 工程）

Hub 里：**Add → 选内层 `quest mirror unity` 文件夹**。

---

## Windows 与 WSL 同步（很重要）

在 WSL 改完代码后，Windows Unity **不会自动更新**。每次改完在 WSL 运行：

```bash
~/vr/scripts/sync_unity_to_windows.sh
```

或在 Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\setup_quest_mirror_unity.ps1
```

---

## 一次性构建完整场景

1. 打开**内层** Unity 工程（见上）
2. 等脚本编译完成（Console 无红错）
3. 菜单：**`Sonic Quest Mirror` → `Build Everything (Complete — Meshes + Scene)`**

成功后会生成：
- `Assets/Robot/G1/G1AvatarFull.prefab`（49 link 真实 mesh）
- `Assets/Scenes/QuestMirrorMain.unity`（网格地面 + 围墙 + G1 + HUD）

4. 点 **Play**
5. WSL（Editor 本机联调可用 `127.0.0.1`）：

```bash
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
cd ~/vr/sonic-bridge
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
python -m sonic_bridge.run_bridge --synthetic --udp-host 127.0.0.1
```

终端按键：`c` = 右扳机校准，`y` = 切换 CALIBRATION/TELEOP（需 Align + 已校准），`x` = 录制。

**推荐：键盘遥操（替代 Quest 双手 EEF）** — 见 [`KEYBOARD_TEST.md`](KEYBOARD_TEST.md)：

```bash
python -m sonic_bridge.run_bridge --keyboard --udp-host 127.0.0.1
```

左手 `QWEASD`、右手 `IOPL;`、头显 `F/J`、校准 `C`、模式 `Y`、录制 `X`、重置 `R`、帮助 `H`。

### 校准流程（头显内）

1. **CALIBRATION**：半透明块 = MuJoCo 幽灵腕（`g1_ref`）；实心块 = 未校准手柄（`vr_3pt_raw`）
2. 把手柄物理对准幽灵，看 HUD **Align** 变绿
3. **右扳机** → SONIC 真校准（HUD 显示「Sonic 已校准」）
4. **Y** → 进入 **TELEOP**（纯 MuJoCo 镜像 + 右下角 D435 PiP）
5. **Y** 可随时回到校准层（不影响 SONIC offset）

---

## 与 MuJoCo 场景对齐（quest_lab）

MuJoCo 与 Unity 共用 **`scene_quest_lab.xml`** + **`MujocoSceneLayout.json`**：

| 物体 | MuJoCo 世界坐标 (x,y,z) m |
|------|---------------------------|
| 机器人 pelvis 初始 | (0, 0, **0.793**) |
| 桌面 table_top | (0.6, 0, 0.7) |
| 盘子 plate | (0.35, 0, 0.735) |
| 水龙头 faucet | (0.6, 0, 1.05) |
| 门 door | 左侧墙 y≈2.45 |

**坐标转换**：MuJoCo (X前 Y左 Z上) → Unity (X右 Y上 Z前)：`PoseMath.MuJoCoToUnityPosition` 使用 `(-y, z, x)`，旋转 `Euler(0,90,0)*Euler(-90,0,0)`。

### MuJoCo 仿真（T1）

默认 WBC yaml 已改为 `scene_quest_lab.xml`：

```bash
python gear_sonic/scripts/run_sim_loop.py --interface eth2
```

### Unity 重建场景

```bash
# WSL
python -m sonic_bridge.scene_layout   # 生成 Resources/MujocoSceneLayout.json
~/vr/scripts/sync_unity_to_windows.sh
```

Unity：**Build Everything (Complete)** → Play + `run_bridge --synthetic`

---

| 菜单 | 作用 |
|------|------|
| `1) Import G1 Meshes & Build Prefab` | 仅导入 mesh、生成 Prefab |
| `2) Build Complete Scene` | 仅建场景（需 Prefab 已存在） |
| **`Build Everything (Complete — Meshes + Scene)`** | **推荐：上面两步合一** |

Mesh 缺失时在 WSL：

```bash
python3 ~/vr/scripts/export_g1_meshes_to_unity.py
~/vr/scripts/sync_unity_to_windows.sh
```

---

## 画面进 Quest 头显（两种方案）

### 方案 A — Quest Link（推荐，与 T3 teleop 共存）

T3 继续用 Quest 上的 **meta_quest_teleop** 发手柄数据；Unity 在 **Windows PC** 上 Play，经 Link 把画面投到头显。

1. Quest 开启 **Quest Link**（有线/ Air Link），PC 安装 Meta Quest Link
2. Unity：**Edit → Project Settings → XR Plug-in Management**
   - **PC, Mac & Linux Standalone** → 勾选 **OpenXR**
   - **OpenXR → Interaction Profiles** 添加 Meta Quest 控制器
3. Windows 跑 relay + Unity Play（见 `PIPELINE.md` T4）
4. 头显里看到的就是 PC Unity 画面；**头追由 Quest XR 负责**（`OperatorCameraRig` 检测到 XR 后不再用 UDP 头部位姿）

### 方案 B — Quest APK（独立 App）

菜单：**`Sonic Quest Mirror` → `3) Configure Android`** → **`4) Build Quest APK`**

```powershell
adb install -r Builds/QuestMirror.apk
```

T4 发 UDP 到 Quest IP（不是 Windows）：

```bash
python -m sonic_bridge.run_bridge --keyboard-file /tmp/sonic_quest_sample.json \
  --udp-host 192.168.0.101 --tcp-relay-port 17782
```

**限制**：Quest 前台只能一个 App。打开 Mirror APK 会挤掉 **meta_quest_teleop**，T3 断流。仅适合无 T3 的纯镜像测试。

---

## 视角与显示（本次修复）

| 问题 | 修复 |
|------|------|
| 主视角歪斜 | `unity_head_pose` 仅驱动 Unity FPV；T3 `vr_3pt` 头行恢复 **固定默认** |
| 右下角 MuJoCo PiP 倒置 | D435 相机加光学帧 180° 修正 |
| 手是方块不是灵巧手 | Bridge 发 `left_hand_display` / `right_hand_display`（掌骨+手指 mesh）；Unity `G1HandMeshRig` 替换腕部方块 |

---

## Hierarchy 检查

构建成功后应有：

```
Environment/
  Ground_Grid, Wall_*, table, ...
RobotRoot/
  G1Avatar/          （49 link mesh，visual_links 驱动）
  CalibrationGroup/  （LeftGhost, RightGhost）
  TeleopGroup/       （RigLines, ErrorArrows）
  RawLeftWrist / RawRightWrist   （G1HandMeshRig 灵巧手 mesh，非方块）
  FpvCamera          （OperatorCameraRig 驱动 / XR 时解耦）
SpectatorCamera
SonicNetwork         （UDP + 全部 View 组件）
TeleopHudCanvas      （状态 HUD + 右下角 D435 PiP）
```

---

## 仍只有 Editor UDP Test？

1. 确认路径是 **`quest mirror unity` 内层**
2. 运行 sync 脚本（见上）
3. Unity 菜单 **Assets → Refresh**，或重启 Unity
4. 看 Console 是否有编译错误（有错误则菜单不会出现）

完整 pipeline：见 `PIPELINE.md`。
