# AI3618 — Meta Quest 3 × GEAR-SONIC 全身遥操项目

> **给做 PPT / 报告的同学**：本文档是项目总入口，讲清**原理、架构、各模块职责、完整使用方法**。更细的专题见 [`docs/`](docs/) 目录。

---

## 目录

1. [项目一句话](#1-项目一句话)
2. [我们要解决什么问题](#2-我们要解决什么问题)
3. [整体架构](#3-整体架构)
4. [各层原理详解](#4-各层原理详解)
5. [仓库结构](#5-仓库结构)
6. [环境准备](#6-环境准备)
7. [完整联调流程（四终端）](#7-完整联调流程四终端)
8. [按键与操作模式](#8-按键与操作模式)
9. [创新层：sonic-bridge + Unity](#9-创新层sonic-bridge--unity)
10. [无 Quest 时的测试方法](#10-无-quest-时的测试方法)
11. [数据采集与回放](#11-数据采集与回放)
12. [PPT 可写的创新点](#12-ppt-可写的创新点)
13. [常见问题](#13-常见问题)
14. [参考链接与文档索引](#14-参考链接与文档索引)

---

## 1. 项目一句话

在 **NVIDIA GEAR-SONIC（GR00T 全身控制栈）** 之上，用 **Meta Quest 3 手柄** 遥操 **Unitree G1 人形机器人**，并在头显 / PC 上增加官方方案没有的 **幽灵校准、对齐门控、MuJoCo 镜像、轨迹录制** 能力。

---

## 2. 我们要解决什么问题

### 2.1 背景

- **GEAR-SONIC** 是 NVIDIA 开源的 G1 全身实时控制方案，包含 ONNX 策略推理、locomotion planner、MuJoCo 仿真和 C++ 部署。
- 官方默认遥操硬件是 **PICO 4 + 脚环**，能拿到完整 SMPL 24 关节身体追踪。
- 我们用的是 **Meta Quest 3 + 两个手柄**，没有脚环，只能做 **VR 3-Point（三点）**：左腕、右腕、固定头部参考。

### 2.2 官方 Quest 路径的缺口

| 缺口 | 我们的补法 |
|------|-----------|
| Quest 上只有黑色 teleop APK，**看不到 G1** | Unity 头显镜像 + MuJoCo FPV |
| 校准只在 PC PyVista 窗口，头显内无引导 | **In-Headset Ghost Calibration**（半透明幽灵腕） |
| 无安全门控，误触就进遥操 | **Pose Alignment Score**，偏差过大拒绝切换 |
| 无结构化遥操数据 | **JSONL 轨迹录制 + MuJoCo 回放** |
| WSL→Windows UDP 不稳定 | **TCP relay** 中继 |

### 2.3 与上游的关系

```
NVIDIA GR00T-WholeBodyControl（官方）
    └── Quest fork: josue99999/TELEOPERATION_SONIC（PR #65）
            └── 本仓库 /home/leon_/vr（AI3618 创新层）
```

- **GR00T 仓库**（`~/projects/GR00T-WholeBodyControl`）：仿真、deploy、Quest reader、ZMQ 协议——**控制链核心，需单独 clone**。
- **本仓库 `vr/`**：sonic-bridge、Unity 工程、脚本、中文文档——**可视化 + 安全 + 数据层**。

---

## 3. 整体架构

### 3.1 四终端流水线

联调时需要 **4 个终端**（T1–T4），各司其职：

```
┌─────────────────────────────────────────────────────────────────┐
│  Meta Quest 3                                                   │
│  ┌──────────────────────┐                                       │
│  │ meta_quest_teleop APK │ ← ADB USB/WiFi，独占连接              │
│  │ (手柄 6DOF + 按键)     │                                       │
│  └──────────┬───────────┘                                       │
└─────────────┼───────────────────────────────────────────────────┘
              │ ADB
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  WSL / Ubuntu                                                   │
│                                                                 │
│  T3: pico_manager_thread_server.py  (--reader quest)            │
│      • 读 Quest 数据、状态机、手 IK                              │
│      • 写 /tmp/sonic_quest_sample.json（给 T4 读）               │
│      • ZMQ PUB :5556 → command / planner / pose                 │
│              │                                                  │
│              ▼                                                  │
│  T2: g1_deploy_onnx_ref  (--input-type zmq_manager)             │
│      • C++ ONNX 策略 + locomotion planner                       │
│      • ZMQ SUB :5556，PUB :5557 (g1_debug 反馈)                 │
│              │                                                  │
│              ▼ Unitree SDK2 (DDS)                               │
│  T1: run_sim_loop.py                                            │
│      • MuJoCo 200Hz 物理仿真，G1 29-DOF                         │
│                                                                 │
│  T4: sonic-bridge (run_bridge.py)  ← 我们的创新层               │
│      • 读 sample JSON + ZMQ g1_debug                            │
│      • G1 FK → visual_links                                     │
│      • alignment_score、录制                                    │
│      • UDP :17771 → Unity                                       │
└─────────────────────────────────────────────────────────────────┘
              │ UDP / TCP relay
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Windows PC                                                     │
│  Unity (quest-mirror-unity 或 quest-mujoco-vr)                  │
│  • G1 49-link mesh 镜像                                         │
│  • 幽灵校准 UI、HUD、延迟条                                      │
│  • 可选 Quest Link 投屏到头显                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 控制链 vs 显示链（重要）

| 链路 | 路径 | 作用 |
|------|------|------|
| **控制链** | Quest → T3 → ZMQ → T2 → T1/真机 | **真正驱动机器人**，缺一不可 |
| **显示链** | T3 sample + T2 反馈 → T4 bridge → Unity | **仅可视化/校准/录制**，不影响控制 |

**T3 独占 Quest ADB**；T4 **不能**再开 `--quest-ip`，只能读 `/tmp/sonic_quest_sample.json`。

---

## 4. 各层原理详解

### 4.1 Quest 数据采集（meta_quest_teleop）

- Quest 3 安装 **meta_quest_teleop** 小 APK（SONIC install 脚本自动装）。
- PC/WSL 通过 **ADB**（USB 或 WiFi `adb connect <Quest_IP>:5555`）读取手柄数据。
- Python 包 `MetaQuestReader` 输出：
  - 左右控制器 **6DOF 位姿**（位置米 + 四元数）
  - 扳机、握把、摇杆、A/B/X/Y 等按键
- 坐标系：**ROS 约定** — X 前、Y 左、Z 上（与 MuJoCo/URDF 一致）。

**代码位置**（GR00T 仓库）：
- `gear_sonic/utils/teleop/readers/quest_reader.py`

### 4.2 VR 3-Point 格式（vr_3pt_pose）

Quest 没有全身体追踪，SONIC 用 **3 个 7D 位姿** 描述上半身：

| 行 | 含义 | 格式 |
|----|------|------|
| 0 | 左腕 L-Wrist | `[x, y, z, qw, qx, qy, qz]` |
| 1 | 右腕 R-Wrist | 同上 |
| 2 | 头部 Head | Quest 无可靠头追时用 **固定默认 pose** |

### 4.3 腕部校准（Quest and 右扳机）

1. 启动时，Manager 用 G1 正向运动学（FK）算出 **默认站立姿态下的左右腕 pose**，作为 `home`。
2. 操作者把手柄物理摆到与 G1 默认腕对齐。
3. **右扳机** 上升沿触发校准：
   ```
   left_offset  = home_left  @ inv(left_raw)
   left_pose    = left_offset @ left_raw   （之后每帧）
   ```
4. 校准后的 `vr_3pt_pose` 经 ZMQ 发给 deploy，驱动 G1 上半身。

**Unity 里的「对准幽灵」只是视觉引导；必须右扳机才写入 SONIC offset。**

### 4.4 Python Manager（T3）

**程序**：`gear_sonic/scripts/pico_manager_thread_server.py`

职责：
- 读 Quest（或 keyboard 调试模式）
- **状态机**：OFF → PLANNER → VR_3PT / POSE
- **灵巧手 IK**：扳机/握把 → `G1GripperIKSolver` → 7-DOF 手关节 → ZMQ `pose`
- **ZMQ 发布**（`:5556`，msgpack）：
  - `command`：start/stop、是否 planner 模式
  - `planner`：下肢走路/转向 + VR 3PT 上半身
  - `pose`：全 body 关节（Protocol v3）
- 导出 sample 到 `/tmp/sonic_quest_sample.json` 供 T4 读取

### 4.5 ZMQ 协议（Python ↔ C++）

| 端口 | Topic | 方向 | 内容 |
|------|-------|------|------|
| **5556** | `command` | Python→C++ | 启停、planner 开关 |
| **5556** | `planner` | Python→C++ | locomotion + vr_3pt |
| **5556** | `pose` | Python→C++ | 全 body SMPL 关节 |
| **5557** | `g1_debug` | C++→Python | 实测关节 body_q 等 |

C++ 侧：`gear_sonic_deploy/.../zmq_manager.hpp` 订阅并喂给 ONNX policy。

### 4.6 C++ Deploy（T2）

**程序**：`gear_sonic_deploy/deploy.sh sim --input-type zmq_manager`

- 加载 ONNX 策略 + TensorRT（或 CPU）locomotion planner
- 50Hz 控制循环
- 输出电机指令 → Unitree SDK2 DDS → MuJoCo 或真机 G1

### 4.7 MuJoCo 仿真（T1）

**程序**：`gear_sonic/scripts/run_sim_loop.py`

- 200Hz 物理步进
- 场景：`scene_quest_lab.xml`（厨房/实验台，pelvis 初始高度 0.793m）
- SDK2 bridge：与 deploy 通过 DDS 通信

### 4.8 sonic-bridge（T4，本仓库核心）

**程序**：`python -m sonic_bridge.run_bridge`

数据流：
```
/tmp/sonic_quest_sample.json  ──┐
ZMQ :5557 g1_debug            ──┼→ G1 FK → visual_links, robot_actual
                                  │
                                  ├→ alignment_score（raw 腕 vs g1_ref）
                                  ├→ JSONL 录制
                                  └→ UDP JSON :17771 → Unity
```

**关键模块**（`sonic-bridge/sonic_bridge/`）：

| 文件 | 作用 |
|------|------|
| `run_bridge.py` | 主循环，~30–60 Hz |
| `g1_fk.py` | Pinocchio/MuJoCo FK，算 49 link 位姿 |
| `alignment.py` | 对齐分数（0–1），超阈值才允许 TELEOP |
| `protocol.py` | UDP JSON 包格式 |
| `recorder.py` | JSONL 轨迹写入 |
| `mujoco_replay.py` | 离线回放 → ZMQ 或 Unity |
| `zmq_feedback.py` | 读 deploy 反馈 |
| `keyboard_teleop.py` | 无 Quest 键盘调试 |

### 4.9 Unity 显示层

两个 Unity 工程：

| 版本 | 路径 | 状态 |
|------|------|------|
| **v1** | `quest-mirror-unity/quest mirror unity` | 功能完整，维护中 |
| **v2** | `quest-mujoco-vr/quest mujoco vr` | 新架构，`hmd_view_pose` 相机 |

Unity 收到 UDP 包后：
- `VisualLinksParser.cs` 解析 49 link 位姿，驱动 G1 mesh
- `GhostCalibrationView` 显示半透明幽灵腕（校准模式）
- `TeleopHud` 显示 Align 分数、延迟、模式
- `MujocoFrame.cs` 做 **MuJoCo→Unity 坐标变换**（唯一允许的一次变换）

**坐标变换**（详见 `docs/COORDINATE_SYSTEMS.md`）：
```
MuJoCo (X前 Y左 Z上) → Unity (X右 Y上 Z前)
位置: p_unity = (-y_m, z_m, x_m)
```

---

## 5. 仓库结构

```
vr/
├── README.md                 ← 本文档
├── OPEN_UNITY_HERE.txt       ← Unity 工程入口提示
├── VR proj.pdf               ← 项目说明 PDF（如有）
│
├── docs/                     ← 专题文档（安装、协议、联调）
│   ├── SETUP_WSL.md          WSL + SONIC 安装
│   ├── DEMO_CHECKLIST.md     第一次联调 checklist
│   ├── PIPELINE.md           完整 pipeline + 按键
│   ├── PROTOCOL.md           UDP JSON 协议
│   ├── COORDINATE_SYSTEMS.md 坐标系（必读）
│   ├── UNITY_SETUP.md        Unity v1 搭建
│   ├── UNITY_V2_SETUP.md     Unity v2 搭建
│   ├── KEYBOARD_TEST.md      键盘无 Quest 测试
│   ├── SONIC_CODE_NOTES.md   GR00T 代码阅读笔记
│   └── ...
│
├── sonic-bridge/             ← Python 创新桥接（T4）
│   ├── sonic_bridge/         源码
│   ├── recordings/           轨迹 JSONL（演示数据）
│   └── requirements.txt
│
├── quest-mirror/             ← Quest 脚本（旧，参考用）
├── quest-mirror-unity/       ← Unity v1 完整工程
│   └── quest mirror unity/   ★ 必须打开内层文件夹
├── quest-mujoco-vr/          ← Unity v2 工程（新）
│   └── quest mujoco vr/
│
├── scripts/                  ← 一键脚本
│   ├── run_sim_t1_wsl.sh     T1 仿真
│   ├── run_bridge_unity_win.sh  T4 bridge
│   ├── wsl_dds_env.sh        DDS 环境变量
│   ├── unity_udp_relay.ps1   Windows UDP 中继
│   └── sync_unity_to_windows.sh  WSL→Windows 同步
│
└── vendor/                   （可选）GR00T 软链接说明
```

**不在本 zip 内、需单独获取：**
- `~/projects/GR00T-WholeBodyControl` — clone 自 [TELEOPERATION_SONIC](https://github.com/josue99999/TELEOPERATION_SONIC)
- TensorRT 安装包（仿真 deploy 用 GPU 时需要）

---

## 6. 环境准备

### 6.1 硬件

| 设备 | 要求 |
|------|------|
| PC | Windows + WSL2 Ubuntu，NVIDIA GPU（RTX 4070 已验证） |
| Quest 3 | 开发者模式，USB 调试或 WiFi ADB |
| 网络 | Quest 与 PC **同一 WiFi**（记下 Quest IP） |

### 6.1 软件（WSL）

```bash
# 1. 系统依赖
sudo apt install -y git git-lfs build-essential python3-pip \
  libgl1 libegl1 libx11-6 android-tools-adb

# 2. Clone SONIC（Quest 分支）
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/josue99999/TELEOPERATION_SONIC.git GR00T-WholeBodyControl
cd GR00T-WholeBodyControl && git lfs pull

# 3. 安装 teleop / sim 环境（约 30–60 分钟）
bash install_scripts/install_pico.sh
bash install_scripts/install_mujoco_sim.sh

# 4. 安装本仓库 bridge
ln -sfn /path/to/vr ~/vr   # 或解压 zip 后 ln -s
cd ~/vr/sonic-bridge
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
pip install -r requirements.txt && pip install -e .
```

详细步骤见 [`docs/SETUP_WSL.md`](docs/SETUP_WSL.md) 或 [`docs/COPY_INSTALL.md`](docs/COPY_INSTALL.md)（ZIP 安装）。

### 6.2 Windows 侧

- **ADB**：`winget install Google.PlatformTools`
- **Unity Hub + Unity 2022.3 LTS**（打开 `quest mirror unity` 内层工程）
- **Meta Quest Link**（可选，PC 画面投到头显）

### 6.3 每次启动 WSL 后

```bash
# DDS 缓冲区（必做，否则 deploy 可能卡住）
sudo sysctl -w net.core.rmem_max=2097152 net.core.rmem_default=2097152 \
              net.core.wmem_max=2097152 net.core.wmem_default=2097152

# 环境变量（T1/T2/T4 都要 source）
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
```

---

## 7. 完整联调流程（四终端）

### Step 0：确认 Quest 连通

```bash
adb connect 192.168.x.x:5555   # 替换 Quest IP
adb devices                    # 应显示 device
python gear_sonic/utils/teleop/readers/test_quest_meta_quest.py --ip-address 192.168.x.x
# 期望: L:OK R:OK，移动手柄坐标变化
```

### Step 1：T1 — MuJoCo 仿真

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

~/vr/scripts/run_sim_t1_wsl.sh
# 或: python gear_sonic/scripts/run_sim_loop.py --interface eth2
```

等待 MuJoCo 窗口出现 G1 站立。

### Step 2：T2 — C++ Deploy

```bash
source ~/vr/scripts/wsl_dds_env.sh
cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy
source scripts/setup_env.sh
./deploy.sh sim --input-type zmq_manager
# 等到终端输出 "Init done"
```

### Step 3：T3 — Quest Manager（独占 Quest）

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

python gear_sonic/scripts/pico_manager_thread_server.py \
  --manager \
  --reader quest \
  --quest-ip-address 192.168.x.x \
  --vis_vr3pt
```

### Step 4：T4 — Bridge + Unity

**WSL（T4）：**
```bash
~/vr/scripts/run_bridge_unity_win.sh
```

**Windows PowerShell（UDP 中继，WSL→Windows 常需）：**
```powershell
powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\unity_udp_relay.ps1
```

**Unity：**
1. 打开 `quest-mirror-unity/quest mirror unity`（内层）
2. 菜单 **Sonic Quest Mirror → Build Everything (Complete)**
3. 点 **Play**

### Step 5：操作演示

1. Unity **CALIBRATION** 模式：对准半透明幽灵腕
2. **右扳机** → SONIC 腕校准（HUD 显示「已校准」）
3. **X**（T3）启动 policy
4. **左摇杆 Click** → 进入 **VR_3PT** 遥操
5. 动手柄 → MuJoCo G1 上半身跟动；左摇杆走、右摇杆转

完整 checklist：[`docs/DEMO_CHECKLIST.md`](docs/DEMO_CHECKLIST.md)

---

## 8. 按键与操作模式

### 8.1 SONIC 官方模式（T3 Manager）

| 模式 | 进入方式 | 机器人行为 |
|------|----------|------------|
| **OFF** | 初始 / A+B+X+Y 急停 | 策略不运行 |
| **PLANNER** | 校准后默认 | 下肢 planner 走路 |
| **VR_3PT** | PLANNER 下 **左摇杆 Click** | 下肢 planner + 上半身跟手柄 |
| **POSE** | **A+X** | 全 body SMPL 跟踪 |

### 8.2 Quest 手柄映射

| 按键 | 作用 | 层级 |
|------|------|------|
| **右扳机** | 腕部校准（首次；重校：Menu+右扳机） | SONIC 控制 |
| **X** | 启动/停止 policy | SONIC 控制 |
| **左摇杆 Click** | 进入/退出 VR_3PT | SONIC 控制 |
| **左/右摇杆** | 走/转（PLANNER 模式） | SONIC 控制 |
| **扳机/握把** | 灵巧手开合（IK） | SONIC 控制 |
| **Y** | Unity CALIBRATION ↔ TELEOP 显示切换 | 仅 Unity 显示 |
| **左握把+Y** | T4 JSONL 录制开/关 | bridge 录制 |

### 8.3 灵巧手原理

```
Quest trigger/grip
  → Manager generate_finger_data (25×4×4 指尖目标)
  → G1GripperIKSolver
  → left/right_hand_joints (7-DOF)
  → ZMQ pose → deploy → MuJoCo 仿真手
```

---

## 9. 创新层：sonic-bridge + Unity

### 9.1 校准流程（头显内）

```
CALIBRATION 模式
  ├─ 半透明块 = g1_ref（G1 默认/仿真腕 pose，MuJoCo FK）
  ├─ 实心块   = vr_3pt_raw（Quest 原始腕，未校准）
  └─ HUD Align 分数 = raw 腕 vs g1_ref 的偏差

操作：对准幽灵 → Align 变绿 → 右扳机 → Y 切 TELEOP
```

### 9.2 TELEOP 模式

- 关幽灵，纯 MuJoCo G1 镜像（`visual_links` 驱动 49 link mesh）
- 右下角 PiP：胸载 D435 相机视锥
- 主视角：Quest Link XR 头追，或 Editor 用 `mirror_camera_pose`

### 9.3 UDP 协议摘要

端口 **17771**，JSON，~30 Hz。主要字段：

| 字段 | 含义 |
|------|------|
| `display_mode` | `CALIBRATION` / `TELEOP` |
| `alignment_score` | 0–1，越高越对齐 |
| `safe_to_switch` | 是否允许切 TELEOP |
| `g1_ref` | 幽灵腕 pose |
| `vr_3pt_raw` / `vr_3pt` | 未校准/已校准 Quest 腕 |
| `visual_links` | 49 link FK（G1 mesh） |
| `robot_joints` | 29 body 关节角 |
| `latency_ms` | 端到端延迟 |

完整协议：[`docs/PROTOCOL.md`](docs/PROTOCOL.md)

### 9.4 Unity 工程打开方式

| 你看到的菜单 | 说明 |
|-------------|------|
| `Build Everything (Complete)` | ✅ 正确 — v1 完整版 |
| `Setup Scene (Editor UDP Test)` | ❌ 开错工程了 |

**必须打开内层文件夹：**
- Windows: `...\vr\quest-mirror-unity\quest mirror unity`
- WSL: `~/vr/quest-mirror-unity/quest mirror unity`

WSL 改代码后同步到 Windows：
```bash
~/vr/scripts/sync_unity_to_windows.sh
```

详见 [`docs/UNITY_SETUP.md`](docs/UNITY_SETUP.md)

### 9.5 头显看画面的两种方式

| 方案 | 做法 | 适用 |
|------|------|------|
| **Quest Link** | Unity 在 PC Play，Link 投屏 | ✅ 推荐，与 T3 teleop 共存 |
| **Quest APK** | Build Android 装头显 | ⚠️ 会挤掉 meta_quest_teleop，T3 断流 |

---

## 10. 无 Quest 时的测试方法

### 10.1 键盘遥操（推荐）

```bash
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
cd ~/vr/sonic-bridge

python -m sonic_bridge.run_bridge --keyboard --udp-host 127.0.0.1
```

按键：`QWEASD` 左手、`IOPL;` 右手、`C` 校准、`Y` 模式、`X` 录制、`H` 帮助。

详见 [`docs/KEYBOARD_TEST.md`](docs/KEYBOARD_TEST.md)

### 10.2 合成数据 demo

```bash
python -m sonic_bridge.run_bridge --synthetic --udp-host 127.0.0.1
# 终端: c=校准, y=模式, x=录制
```

### 10.3 仅测 Quest 数据

```bash
python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic --duration 5
python gear_sonic/utils/teleop/readers/validate_quest_raw --calibrated --ip-address 192.168.x.x
```

---

## 11. 数据采集与回放

### 11.1 录制

- **左握把+Y**（T4 bridge）或 **X**（keyboard 模式）开始/停止
- 文件：`sonic-bridge/recordings/session_YYYYMMDD_HHMMSS.jsonl`
- 每行含：`vr_3pt_pose`、`hand_state`、`robot_joints`、`alignment_score` 等

### 11.2 回放

```bash
# 回放 JSONL → ZMQ（需 T1+T2 已跑）
python -m sonic_bridge.mujoco_replay --jsonl recordings/session_xxx.jsonl

# 同时回放给 Unity
python -m sonic_bridge.mujoco_replay --jsonl recordings/session_xxx.jsonl \
  --target both --udp-host 192.168.x.x
```

---

## 12. PPT 可写的创新点

| # | 创新点 | 原理 | 代码位置 |
|---|--------|------|----------|
| 1 | **In-Headset Ghost Calibration** | 头显内显示 G1 半透明幽灵腕，引导物理对齐后再校准 | Unity `GhostCalibrationView.cs` |
| 2 | **Pose Alignment Score** | 量化 Quest 腕与 G1 参考 pose 偏差，超阈值拒绝 TELEOP | `sonic_bridge/alignment.py` |
| 3 | **Trajectory Log / Replay** | JSONL 录制 vr_3pt + 按键 + 关节，MuJoCo 离线回放 | `recorder.py`, `mujoco_replay.py` |
| 4 | **Latency HUD** | ZMQ/UDP 延迟 >30ms 时 Quest UI 警告 | Unity `TeleopHud.cs` |
| 5 | **MuJoCo 场景镜像** | Unity 与 MuJoCo 共用 `scene_quest_lab` 布局 | `scene_layout.py`, `MujocoSceneLayout.json` |
| 6 | **控制/显示解耦** | T3 控机器人，T4 只镜像，避免双 QuestReader 冲突 | `run_bridge_unity_win.sh` |

**对比表（PPT 可用）**：

| | PICO（NVIDIA 官方） | Quest（我们） |
|--|---------------------|---------------|
| 硬件 | PICO 4 + 脚环 | Quest 3 + 手柄 |
| 身体追踪 | SMPL 24 关节 | VR 3PT（双腕+固定头） |
| 可视化 | PC PyVista | + Unity 头显镜像 |
| 校准 | PC 窗口 | + 头显内幽灵引导 |
| 数据 | 官方 NPZ | + JSONL 结构化录制 |

---

## 13. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `adb devices` 空 | WiFi IP 错 / USB 未授权 | 检查 Quest IP；USB 重新插拔 |
| deploy Init 卡住 | TensorRT / DDS 接口 | 检查 GPU；`source wsl_dds_env.sh`；换 `--interface eth2` |
| Unity 收不到 UDP | WSL→Windows 防火墙 | 跑 `unity_udp_relay.ps1`；防火墙放行 17771 |
| 扳机/policy 失效 | T3 和 T4 各开了 QuestReader | T4 **不要** `--quest-ip`，只读 sample 文件 |
| Unity 菜单不对 | 开错工程文件夹 | 必须开 **内层** `quest mirror unity` |
| 手反向 / 坐标乱 | 双重坐标变换 | 读 `COORDINATE_SYSTEMS.md`，勿在 QuestReader 再加变换 |
| Quest 上只有黑屏 teleop | 那是 SONIC APK，不是 Mirror | 需 Unity Link 或单独装 Mirror APK |

---

## 14. 参考链接与文档索引

### 外部

- [NVIDIA GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl)
- [Quest fork / PR #65](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/65)
- [josue99999/TELEOPERATION_SONIC](https://github.com/josue99999/TELEOPERATION_SONIC)

### 本仓库 docs/

| 文档 | 内容 |
|------|------|
| [`SETUP_WSL.md`](docs/SETUP_WSL.md) | WSL 完整安装 |
| [`DEMO_CHECKLIST.md`](docs/DEMO_CHECKLIST.md) | 第一次联调步骤 |
| [`PIPELINE.md`](docs/PIPELINE.md) | Pipeline + 按键 + 录制 |
| [`PROTOCOL.md`](docs/PROTOCOL.md) | UDP JSON 协议全文 |
| [`COORDINATE_SYSTEMS.md`](docs/COORDINATE_SYSTEMS.md) | 坐标系（开发必读） |
| [`UNITY_SETUP.md`](docs/UNITY_SETUP.md) | Unity v1 搭建 |
| [`UNITY_V2_SETUP.md`](docs/UNITY_V2_SETUP.md) | Unity v2 搭建 |
| [`KEYBOARD_TEST.md`](docs/KEYBOARD_TEST.md) | 无 Quest 键盘测试 |
| [`SONIC_CODE_NOTES.md`](docs/SONIC_CODE_NOTES.md) | GR00T 代码阅读 |
| [`COPY_INSTALL.md`](docs/COPY_INSTALL.md) | ZIP 手动安装 |
| [`QUEST_LINK.md`](docs/QUEST_LINK.md) | Quest Link 投屏 |
| [`MUJOCO_FPV_QUEST.md`](docs/MUJOCO_FPV_QUEST.md) | 浏览器 FPV 备选 |

---

**维护**：AI3618 / leon_  
**打包说明**：本 zip 不含 GR00T 主仓库、TensorRT 安装包、Unity `Library/` 缓存；解压后按第 6 节 clone SONIC 并安装 bridge。
