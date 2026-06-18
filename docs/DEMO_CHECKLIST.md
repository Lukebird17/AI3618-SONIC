# 第一次联调 Checklist

## 准备

- [ ] Quest 3 开发者模式 + USB 调试
- [ ] Quest 与 PC **同一 WiFi**（记下 Quest IP：设置 → WiFi → 详情）
- [ ] WSL 已执行 [SETUP_WSL.md](SETUP_WSL.md)
- [ ] `nvidia-smi` 在 WSL 正常

---

## Step 1：仅测 Quest 数据（5 分钟）

```bash
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
cd ~/projects/GR00T-WholeBodyControl

# 合成模式（无 Quest）
python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic --duration 5

# 真机 WiFi（替换 IP）
python gear_sonic/utils/teleop/readers/test_quest_meta_quest.py --ip-address 192.168.x.x
```

期望：`L:OK R:OK`，移动手柄坐标变化。

---

## Step 2：PC 3D 校准可视化

```bash
python -m gear_sonic.utils.teleop.readers.validate_quest_raw --calibrated --ip-address 192.168.x.x
```

1. 看 G1 默认腕 pose  
2. 手柄对齐 → **右扳机**  
3. 移动手柄，PyVista 里绿/蓝球跟手  

---

## Step 3：SONIC 三终端

**T1 — MuJoCo**

```bash
source .venv_teleop/bin/activate   # 或 .venv_sim
python gear_sonic/scripts/run_sim_loop.py
```

**T2 — Deploy**

```bash
cd gear_sonic_deploy
source scripts/setup_env.sh
./deploy.sh sim --input-type zmq_manager
# 等到 "Init done"
```

**T3 — Quest Manager**

```bash
source .venv_teleop/bin/activate
python gear_sonic/scripts/pico_manager_thread_server.py \
  --manager --reader quest --quest-ip-address 192.168.x.x --vis_vr3pt
```

操作：

1. 对齐 G1 默认 pose → **右扳机** 校准  
2. **X** 启动/停止 policy  
3. **左摇杆 Click** 进 VR_3PT  
4. 动手柄 → PC 上 G1 上半身跟动  
5. 左摇杆走、右摇杆转  

---

## Step 4：创新 Bridge + Unity（第四终端）

**两种 Unity 收 UDP 方式（不要混用）：**

| Unity 跑在哪 | `--udp-host` | 头显里看到什么 |
|-------------|--------------|----------------|
| **Windows Editor Play**（推荐先联调） | PC 局域网 IP（Windows `ipconfig` 里 192.168.x.x，**不是 Quest IP**） | PC 显示器；可用 Quest Link 看 PC 画面 |
| **Quest 上 Quest Mirror APK**（需 Unity Build Android 并 `adb install`） | Quest IP（如 192.168.0.101） | 头显内 G1 校准/FPV |

> **常见误区**：Quest 上只有 **meta_quest_teleop**（SONIC 黑屏）时，T4 即使用 `--udp-host <Quest_IP>` 也**不会有 G1 UI**——那个 APK 不监听 17771。必须另装 **Quest Mirror** Unity App。

**T4 — Bridge**（T3 必须先跑；T4 **不要** `--quest-ip`）

```bash
~/vr/scripts/run_bridge_unity_win.sh
# Windows: powershell -File C:\File\vr\scripts\unity_udp_relay.ps1
```

> T3 与 T4 不能各开一个 QuestReader，否则扳机/policy 会失效。T3 写 `/tmp/sonic_quest_sample.json`，T4 只读该文件。

**T4 — Bridge**（旧写法，会抢 Quest，勿用）

```bash
python -m sonic_bridge.run_bridge --quest-ip 192.168.x.x --udp-host 192.168.x.x
```

应看到：幽灵 G1 腕、`alignment_score` HUD、延迟条。  

---

## Step 5：录 Demo

- [ ] PC 录 MuJoCo 窗口 30s  
- [ ] 录 Quest 内 Mirror UI 15s  
- [ ] 展示轨迹回放：`python -m sonic_bridge.replay --file recordings/xxx.jsonl`

---

## 常见错误

| 现象 | 处理 |
|------|------|
| No devices found | WiFi IP 是否正确；或 USB + adb devices |
| meta_quest_teleop 未安装 | 重跑 install_pico.sh |
| deploy Init 卡住 | 检查 checkpoint / TensorRT；换 CPU 模式 |
| 手反向 | validate_quest_raw --calibrated 先验证 |
| Unity 收不到 UDP | Windows 防火墙放行 17771；Quest 与 PC 同网 |
