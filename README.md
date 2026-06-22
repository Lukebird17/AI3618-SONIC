# AI3618-SONIC — 虚拟现实课程大作业

> **基于Meta Quest 3的SONIC人形机器人遥操系统复现与增强**

## 项目简介

本项目基于NVIDIA GR00T-WholeBodyControl项目的[Quest支持PR(#65)](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/65)，在SONIC全身遥操框架上，使用Meta Quest 3实现了对Unitree G1人形机器人的三点（双腕+固定头）遥操控制，并在此基础上增加了**可视化镜像、引导式校准、数据录制与回放**等创新功能。

**演示视频**：已通过课上展示完成演示。


## 核心功能

### 1. 三点遥操接入（基础复现）

- Quest 3手柄数据通过ADB/WiFi接入
- 生成`vr_3pt_pose`（左腕、右腕、固定头）
- 经ZMQ发送至deploy，驱动MuJoCo中的G1机器人
- 保留SONIC原有控制主链路

三点遥操接入是后续bridge和demo的基础。

### 2. 让遥操"看得见"（创新）

原控制过程对操作者接近黑盒。为此新增`sonic-bridge`中间层：

- 读取T3 manager的Quest原始输入
- 订阅T2 deploy发布的`g1_debug`反馈（关节状态）
- 计算G1各部位（手腕、头部、躯干、D435相机）的FK位姿
- 输出结构化`BridgeState`：
  - Quest原始三点输入
  - G1实际关键部位位姿
  - link级可视化位姿
  - 输入与机器人状态之间的偏差

这些状态数据可用于终端调试、JSONL回放和Unity显示。

### 3. 引导式校准（创新）

操作者很难判断人手和机器人默认腕部姿态是否对齐。为此：

- **校准虚像**：在Unity原型中显示目标腕部位置（半透明幽灵腕）
- **对齐分数**：计算手柄腕部与参考腕部的差距（0-1）
- **Safe-to-switch**：当对齐达标并完成Trigger校准后，显示层才建议进入TELEOP

将校准变成可量化、有视觉引导的流程，减少误操作风险。

### 4. 演示可复现（创新）

- `sonic-bridge`结构化记录轨迹（JSONL格式）
- 数据包含：vr_3pt、手部状态、机器人关节、对齐分数等
- 支持离线回放（`mujoco_replay.py`）

### 探索尝试：第一人称观察

- 尝试将Quest头显旋转映射为Unity可旋转观察点
- 实现G1头部FK + Quest HMD session增量的相机驱动原型
- **当前结论**：延迟过高，未稳定调通，作为探索尝试保留


## 系统架构

核心设计原则：**控制链和显示链分离**。控制闭环保持稳定，显示层独立叠加，即使显示层崩溃，机器人控制也不受影响。

```
┌─────────────┐
│  Quest 3    │
│  (手柄6DOF) │
└──────┬──────┘
       │ ADB/WiFi
       ▼
┌─────────────────────────────────────────────────────────────────┐
│                        控制链                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ T3: pico_manager_thread_server.py (Quest reader)       │    │
│  │     • 读手柄数据、状态机、手IK                          │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       │ ZMQ :5556                              │
│                       ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ T2: g1_deploy_onnx_ref (C++)                           │    │
│  │     • ONNX策略 + locomotion planner                    │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       │ DDS                                    │
│                       ▼                                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ T1: run_sim_loop.py (MuJoCo 200Hz)                    │    │
│  │     • G1 29-DOF物理仿真                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                               │
│  ZMQ :5557 (g1_debug反馈) ────────────────────────┐           │
│  T3样例 (/tmp/sonic_quest_sample.json) ────────┐  │           │
│                                                 │  │           │
│                      显示链                      ▼  ▼           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ T4: sonic-bridge (Python)  ← 我们新增的中间层          │    │
│  │     • 读Quest sample + g1_debug反馈                    │    │
│  │     • G1 FK → visual_links                            │    │
│  │     • alignment_score、录制                           │    │
│  │     • 生成BridgeState                                 │    │
│  └────────────────────┬────────────────────────────────────┘    │
│                       │ UDP :17771 / TCP relay                 │
└───────────────────────┼─────────────────────────────────────────┘
                        ▼
              ┌─────────────────────┐
              │   Unity Prototype   │
              │ (只负责观察/展示/   │
              │  校准/录制)         │
              └─────────────────────┘
```

**控制链**（SONIC原有）：Quest → T3 → ZMQ → T2 → T1  
**显示链**（我们新增）：T3 sample + T2反馈 → T4 bridge → Unity


## 快速开始

### 环境准备

**硬件要求：**

| 设备 | 要求 |
|------|------|
| PC | Windows + WSL2 Ubuntu，NVIDIA GPU（RTX 4070 已验证） |
| Quest 3 | 开发者模式，USB 调试或 WiFi ADB |
| 网络 | Quest 与 PC **同一 WiFi**（记下 Quest IP） |

**WSL 侧安装：**

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
cd ~/vr/sonic-bridge
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
pip install -r requirements.txt && pip install -e .
```

**Windows 侧：**

- ADB：`winget install Google.PlatformTools`
- Unity Hub + Unity 2022.3 LTS（打开 `quest-mirror-unity/quest mirror unity` 内层工程）
- Meta Quest Link（可选，PC 画面投到头显）

**每次启动 WSL 后：**

```bash
# DDS 缓冲区（必做，否则 deploy 可能卡住）
sudo sysctl -w net.core.rmem_max=2097152 net.core.rmem_default=2097152 \
              net.core.wmem_max=2097152 net.core.wmem_default=2097152

# 环境变量（T1/T2/T4 都要 source）
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
```

### 四终端联调

**Step 0：确认 Quest 连通**

```bash
adb connect 192.168.x.x:5555   # 替换 Quest IP
adb devices                    # 应显示 device
python gear_sonic/utils/teleop/readers/test_quest_meta_quest.py --ip-address 192.168.x.x
# 期望: L:OK R:OK，移动手柄坐标变化
```

**Step 1：T1 — MuJoCo 仿真**

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

~/vr/scripts/run_sim_t1_wsl.sh
# 或: python gear_sonic/scripts/run_sim_loop.py --interface eth2
```

等待 MuJoCo 窗口出现 G1 站立。

**Step 2：T2 — C++ Deploy**

```bash
source ~/vr/scripts/wsl_dds_env.sh
cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy
source scripts/setup_env.sh
./deploy.sh sim --input-type zmq_manager
# 等到终端输出 "Init done"
```

**Step 3：T3 — Quest Manager（独占 Quest）**

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

**Step 4：T4 — Bridge + Unity**

WSL（T4）：
```bash
~/vr/scripts/run_bridge_unity_win.sh
```

Windows PowerShell（UDP 中继，WSL→Windows 常需）：
```powershell
powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\unity_udp_relay.ps1
```

Unity：
1. 打开 `quest-mirror-unity/quest mirror unity`（内层）
2. 菜单 **Sonic Quest Mirror → Build Everything (Complete)**
3. 点 **Play**

**Step 5：操作演示**

1. Unity **CALIBRATION** 模式：对准半透明幽灵腕
2. **右扳机** → SONIC 腕校准（HUD 显示"已校准"）
3. **X**（T3）启动 policy
4. **左摇杆 Click** → 进入 **VR_3PT** 遥操
5. 动手柄 → MuJoCo G1 上半身跟动；左摇杆走、右摇杆转

### 无Quest测试（键盘模式）

```bash
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
cd ~/vr/sonic-bridge

python -m sonic_bridge.run_bridge --keyboard --udp-host 127.0.0.1
```

按键映射：`QWEASD` 左手、`IOPL;` 右手、`C` 校准、`Y` 模式切换、`X` 录制、`H` 帮助。

合成数据测试模式：
```bash
python -m sonic_bridge.run_bridge --synthetic --udp-host 127.0.0.1
# 终端: c=校准, y=模式, x=录制
```


## 项目结构

```
AI3618-SONIC/
├── docs/                          # 项目文档
│   ├── PIPELINE.md                # 系统流程说明
│   ├── PROTOCOL.md                # 通信协议
│   ├── COORDINATE_SYSTEMS.md      # 坐标系定义
│   ├── UNITY_SETUP.md             # Unity环境配置
│   └── ...                        # 联调与部署文档
│
├── patches/                       # 对GR00T-WholeBodyControl的补丁
│   └── gr00t/
│       └── files/
│           └── gear_sonic/
│               ├── scripts/
│               │   └── pico_manager_thread_server.py
│               ├── utils/
│               │   ├── mujoco_sim/
│               │   └── teleop/
│               └── data/
│                   └── robot_model/
│
├── quest-mirror/                  # Unity可视化与校准系统
│   ├── Assets/
│   │   ├── Scripts/
│   │   │   ├── Calibration/       # 引导式校准
│   │   │   ├── Mirror/            # 镜像显示
│   │   │   ├── Network/           # UDP通信
│   │   │   ├── Protocol/          # 数据协议
│   │   │   ├── Robot/             # G1模型解析
│   │   │   └── UI/                # HUD界面
│   │   ├── Robot/                 # G1网格模型
│   │   ├── Scenes/                # Unity场景
│   │   └── Resources/             # 配置文件
│   └── README.md
│
├── README.md
├── VR proj.pdf                    # 项目报告
└── OPEN_UNITY_HERE.txt            # Unity工程入口
```


## 成员与分工

| 成员 | 分工 |
|------|------|
| 卢鸿良 | 机器人部分代码实现 |
| 方捷、施嘉佑、沈笑 | 机器人代码与Quest连接、PPT |
| 王洋、沈天琦 | Demo录制、数据采集、代码库整理 |


## 技术参考

- [NVIDIA GR00T-WholeBodyControl](https://github.com/NVlabs/GR00T-WholeBodyControl)
- [SONIC Quest PR #65](https://github.com/NVlabs/GR00T-WholeBodyControl/pull/65)
- [josue99999/TELEOPERATION_SONIC](https://github.com/josue99999/TELEOPERATION_SONIC)

