# WSL 安装指南（Ubuntu + RTX 4070）

你的 WSL 已确认：

```powershell
wsl --list --verbose
# * Ubuntu  Stopped  2
```

进入 WSL：

```powershell
wsl -d Ubuntu
```

---

## 0. 每次启动 WSL 后（必做）

```bash
sudo sysctl -w net.core.rmem_max=2097152 net.core.rmem_default=2097152 \
              net.core.wmem_max=2097152 net.core.wmem_default=2097152
```

可写入 `~/.bashrc`：

```bash
echo 'sudo sysctl -w net.core.rmem_max=2097152 net.core.rmem_default=2097152 net.core.wmem_max=2097152 net.core.wmem_default=2097152 2>/dev/null' >> ~/.bashrc
```

---

## 1. 系统依赖

```bash
sudo apt update
sudo apt install -y git git-lfs build-essential curl python3 python3-venv python3-pip \
  libgl1 libegl1 libx11-6 android-tools-adb android-tools-fastboot
```

### Quest USB 权限

```bash
sudo bash -c 'cat > /etc/udev/rules.d/51-android.rules' << 'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="2833", MODE="0666", GROUP="plugdev"
EOF
sudo usermod -aG plugdev $USER
sudo udevadm control --reload-rules && sudo udevadm trigger
```

WSL USB 需 Windows 侧 [usbipd-win](https://github.com/dorssel/usbipd-win)；**优先用 WiFi 连 Quest** 可跳过 USB 透传。

---

## 2. 克隆 SONIC（Quest 支持）

**推荐**（含 Quest 文档与 reader）：

```bash
mkdir -p ~/projects && cd ~/projects
git clone https://github.com/josue99999/TELEOPERATION_SONIC.git GR00T-WholeBodyControl
cd GR00T-WholeBodyControl
git lfs pull
```

或 NVlabs 官方 + PR 分支：

```bash
git clone https://github.com/NVlabs/GR00T-WholeBodyControl.git
cd GR00T-WholeBodyControl
git fetch origin pull/65/head:feature/meta-quest3-support
git checkout feature/meta-quest3-support
git lfs pull
```

---

## 3. 安装 teleop / sim 环境

```bash
cd ~/projects/GR00T-WholeBodyControl
bash install_scripts/install_pico.sh
bash install_scripts/install_mujoco_sim.sh
```

激活：

```bash
source .venv_teleop/bin/activate
```

---

## 4. 验证（无需完整 deploy）

```bash
# 合成数据测 reader
python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic --duration 5

# Quest USB 连接后
python -m gear_sonic.utils.teleop.readers.quest_reader --test-adb

# 可视化 tracking（PC 窗口）
python -m gear_sonic.utils.teleop.readers.validate_quest_raw --calibrated
```

---

## 5. 安装本仓库 bridge

```bash
cd /mnt/c/File/vr/sonic-bridge
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
pip install -r requirements.txt
pip install -e .
```

---

## 6. 完整仿真联调（3+1 终端）

见 [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md)

---

## 路径对照

| Windows | WSL |
|---------|-----|
| `C:\File\vr` | `/mnt/c/File/vr` |
| `C:\Users\leon_` | `/mnt/c/Users/leon_` |
| — | `~/projects/GR00T-WholeBodyControl` |

---

## GPU 说明

你的 RTX 4070 在 WSL 可用。若 C++ deploy TensorRT 安装失败，可先用 sim + CPU ONNX（文档：`deploy.sh sim --input-type zmq_manager`）。

MuJoCo 在 WSL 可能软件渲染（MESA 警告），**不影响逻辑**，窗口慢属正常。
