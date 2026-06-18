# 键盘遥操 — 完整跑通指南（无 Quest）

用键盘替代 Quest，验证 **MuJoCo 真遥操 + Unity 镜像 + 校准/录制** 全链路。

---

## 0. 环境（每个新 WSL 终端）

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
```

快速打印四终端命令：

```bash
bash ~/vr/scripts/print_keyboard_pipeline.sh
```

---

## 1. 修复 `Address already in use :5557`

deploy 第二次启动时，旧进程仍占用 **5557**（`g1_debug`）会崩溃：

```bash
bash ~/vr/scripts/kill_sonic_zmq.sh
```

然后**重新**启动 T2 deploy。T1 MuJoCo 可保持运行。

---

## 2. 四终端 + Unity（完整项目测试）

### Windows — Unity

1. `C:\File\vr\quest-mirror-unity\quest mirror unity`
2. `~/vr/scripts/sync_unity_to_windows.sh`（改过脚本后）
3. **Build Everything (Complete)** → Play

### T1 — MuJoCo（必须先于 T2）

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl
cd ~/projects/GR00T-WholeBodyControl
python gear_sonic/scripts/run_sim_loop.py
```

应弹出 MuJoCo 窗口。

### T2 — Deploy

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy/scripts/setup_env.sh
cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy
./deploy.sh sim --input-type zmq_manager
```

**T1 和 T2 都必须先 `source wsl_dds_env.sh`**。若一直刷 `LowState is not available`，说明 MuJoCo 没连上（T1 未跑或 DDS 网卡不对）。

等到 **Init done** 且无 `Address already in use`（可先 `bash ~/vr/scripts/kill_sonic_zmq.sh`）。

### T3 — Manager + 键盘（唯一读键盘的终端）

```bash
cd ~/projects/GR00T-WholeBodyControl
python gear_sonic/scripts/pico_manager_thread_server.py \
  --manager --reader keyboard --vis_vr3pt
```

写入 `/tmp/sonic_keyboard_sample.json` 供 Unity bridge 读取。

### T4 — Bridge → Unity

```bash
cd ~/vr/sonic-bridge
python -m sonic_bridge.run_bridge \
  --keyboard-file /tmp/sonic_keyboard_sample.json \
  --udp-host 127.0.0.1
```

Windows Unity 用：`WIN_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}')` 替换 `127.0.0.1`。

---

## 3. 键盘映射

| 键 | 作用 |
|----|------|
| **Q/A W/S E/D** | 左手 EEF X/Y/Z ± |
| **I/K O/L P/;** | 右手 EEF X/Y/Z ± |
| **F/J** | 头显绕 Z 左右转 |
| **1** | 启动/停止 policy（A+B+X+Y） |
| **C** | 右扳机 — SONIC 腕校准 |
| **V** | 左摇杆 Click — 进/出 **VR_3PT**（MuJoCo 跟手） |
| **Y** | Unity **CALIBRATION ↔ TELEOP**（仅显示层） |
| **X** | JSONL 录制开/关 |
| **R** | 腕位重置到 G1 默认+偏移 |
| **H** | 打印帮助 |

坐标：MuJoCo pelvis（X 前 Y 左 Z 上）。

---

## 4. 推荐验证流程

### 校准看哪里？（重要）

| 界面 | 用途 | 你应该看到什么 |
|------|------|----------------|
| **Unity（主界面）** | **对准 + Align** | 半透明**幽灵腕**（MuJoCo 参考）+ 实心**黄块**（键盘/raw 腕）；HUD **Align %** |
| **T3 PyVista**（`--vis_vr3pt`） | 可选调试 | 彩色 VR 3-point 标记随 **QWEASD/IOPL;** 移动（已修复） |
| **T1 MuJoCo 窗口** | 跟手验证 | 按 **V** 进 VR_3PT 后，机器人物理手臂才跟键盘动 |
| **T2 Deploy** | 日志 | Init done、模式切换 |

**不要**在 PyVista 或 MuJoCo 里做「对准幽灵再按 C」——那是 **Unity CALIBRATION 层** 的流程。

Unity 若看不到手/幽灵：
1. 确认打开**内层**工程 `quest mirror unity`
2. 菜单 **Build Everything (Complete)** 重建场景（旧场景缺 RawWrist）
3. T4 `--udp-host` 指向 **Windows IP**（不是 WSL 的 127.0.0.1）
4. HUD 不应一直显示 “Waiting for UDP”

MuJoCo 默认已改为**站地**（关闭 virtual elastic band + 站立关节角 + deploy 未连时 PD 持姿）。需**重启 T1** 才生效。

T4 若刷 `FK failed: Expected q of length 43, got 29`：已修复（29 维 body_q 自动扩展为 Pinocchio 43 维）。**重启 T4**。

| 步骤 | 操作 | 期望 |
|------|------|------|
| 1 | T1→T2→T3→T4 + Unity Play | 无报错，HUD 有数据 |
| 2 | T3 按 **1** | Manager 进入 PLANNER（policy 启动） |
| 3 | **QWEASD/IOPL;** | Unity 黄块动；Align 变化 |
| 4 | 对准幽灵 → **C** | Sonic 已校准 |
| 5 | **V** | 进入 VR_3PT；MuJoCo 手臂跟键盘 EEF |
| 6 | T4 **Y**（或 T3 按 Y） | Unity TELEOP 镜像层 |
| 7 | **F/J** | Editor 主视角转 |
| 8 | **X** | `~/vr/sonic-bridge/recordings/*.jsonl` |

---

## 5. 仅 Unity（不跑 MuJoCo）

单终端：

```bash
cd ~/vr/sonic-bridge
python -m sonic_bridge.run_bridge --keyboard --udp-host 127.0.0.1
```

只验 Unity 创新层，机器人不会在 MuJoCo 里动。

---

## 6. 上 Quest 时

T3 改为 `--reader quest`，T4 改为 `--quest-ip <IP>`（去掉 `--keyboard-file`）。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| T2 `:5557` 占用 | `bash ~/vr/scripts/kill_sonic_zmq.sh` |
| T2 `LowState is not available` | T1 先跑；T1/T2 都 `source wsl_dds_env.sh`；deploy 用 `sim`（已自动改 eth2） |
| T3 按键无效 | 焦点在 manager 终端 |
| T4 Unity 无手数据 | T3 是否在跑 keyboard reader |
| VR_3PT 不进 | 先 **1** 启动 policy，再 **C** 校准，再 **V** |
| Y 进不了 TELEOP | 先 Align + **C**，再 **Y** |
