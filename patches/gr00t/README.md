# GR00T / SONIC 补丁（与 `vr` 同仓库）

本目录存放对 [TELEOPERATION_SONIC](https://github.com/josue99999/TELEOPERATION_SONIC) 的**小文件覆盖**，与 `~/vr` 创新层放在**同一个 GitHub 仓库**里。

大文件（ONNX 模型、TensorRT、Unity `Library/`、录制 jsonl）仍在各自目录，**不移动**；由根目录 `.gitignore` 排除，不会 push 到 GitHub。

## 安装顺序

```bash
# 1. Clone 官方 SONIC（或你们的 fork）
git clone https://github.com/josue99999/TELEOPERATION_SONIC.git ~/projects/GR00T-WholeBodyControl
cd ~/projects/GR00T-WholeBodyControl
bash install_scripts/install_pico.sh
bash install_scripts/install_mujoco_sim.sh

# 2. Clone 本仓库（AI3618 创新层 + 补丁）
ln -sfn /path/to/AI3618-Quest-VR-Teleop ~/vr   # 或任意路径

# 3. 打上 GR00T 补丁
~/vr/scripts/apply_gr00t_patches.sh

# 4. 安装 bridge
cd ~/vr/sonic-bridge && pip install -e .
```

## 更新补丁（维护者）

改完 GR00T 源码后，在 `~/vr` 执行：

```bash
~/vr/scripts/export_gr00t_patches.sh
git add patches/gr00t && git commit -m "Update GR00T patches"
```
