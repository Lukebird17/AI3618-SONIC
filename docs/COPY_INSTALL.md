# 手动复制 / ZIP 安装指南

不想 `git clone` 时，用下面任一方式。

---

## 方式 A：一键 ZIP 脚本（推荐）

PowerShell：

```powershell
wsl -d Ubuntu bash /mnt/c/File/vr/scripts/setup_from_zip.sh
```

脚本会：
1. `apt install` 依赖（含 pip、adb、unzip）
2. **curl 下载** [TELEOPERATION_SONIC](https://github.com/josue99999/TELEOPERATION_SONIC) 的 ZIP 到 `~/projects/GR00T-WholeBodyControl`
3. 跑 `install_pico.sh`
4. 把 `C:\File\vr` 软链到 `~/vr`

---

## 方式 B：浏览器下载 ZIP 再复制

### 1. Windows 下载

打开并下载：

https://github.com/josue99999/TELEOPERATION_SONIC/archive/refs/heads/main.zip

解压到例如：

```
C:\File\sonic\TELEOPERATION_SONIC-main\
```

### 2. 复制到 WSL

PowerShell：

```powershell
wsl -d Ubuntu bash -c "mkdir -p ~/projects && cp -r /mnt/c/File/sonic/TELEOPERATION_SONIC-main ~/projects/GR00T-WholeBodyControl"
```

或资源管理器地址栏输入 `\\wsl$\Ubuntu\home\leon_\projects`，手动拖文件夹进去，改名为 `GR00T-WholeBodyControl`。

### 3. 继续安装

```bash
wsl -d Ubuntu
sudo apt install -y python3-pip unzip git git-lfs build-essential android-tools-adb \
  libgl1 libegl1 libx11-6
ln -sfn /mnt/c/File/vr ~/vr
cd ~/projects/GR00T-WholeBodyControl
bash install_scripts/install_pico.sh
source .venv_teleop/bin/activate
pip install -e ~/vr/sonic-bridge
```

---

## 方式 C：只复制我们的项目（SONIC 已有）

若 SONIC 已在 `~/projects/GR00T-WholeBodyControl`：

```bash
ln -sfn /mnt/c/File/vr ~/vr
cd ~/vr/sonic-bridge
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
pip install -e .
```

**不需要**把 `C:\File\vr` 再复制一份；WSL 可直接访问 `/mnt/c/File/vr`。

---

## 路径对照

| Windows | WSL |
|---------|-----|
| `C:\File\vr` | `/mnt/c/File/vr` 或 `~/vr`（软链） |
| `C:\File\sonic\...` | `/mnt/c/File/sonic/...` |
| — | `~/projects/GR00T-WholeBodyControl` |

---

## 验证

```bash
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic --duration 3
python -m sonic_bridge.standalone_demo
```
