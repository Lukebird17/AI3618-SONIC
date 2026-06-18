# 方案 B — Quest 原生 APK（不走 Link）

PC 显示器留给 MuJoCo / 终端；**沉浸 VR 在头显里的 Unity App**，不经过 Quest Link。

## 和 Link 方案对比

| | Quest Link + PC exe | **Quest APK（本方案）** |
|--|---------------------|-------------------------|
| 头显 VR | 依赖 Link + OpenXR PC | 头显内原生 OpenXR |
| PC 屏幕 | 易被 Unity 占满 | **完全自由** |
| T4 数据 | relay + TCP | **UDP 直打 Quest IP** |
| 编译时头显 | 可能黑屏/断 Link | **不受影响** |

## 一次性：Unity 打 APK

1. 工程：`C:\File\vr\quest-mirror-unity\quest mirror unity`
2. **Sonic Quest Mirror → Build Everything (Complete)**
3. **3) Configure Android (Quest) Build Settings**
4. **Edit → Project Settings → XR Plug-in Management → Android**
   - 勾选 **OpenXR**
   - 左侧 **OpenXR → Android** 里勾选 **Meta Quest Support**（仅 Android 有这项）
5. **4) Build Quest APK** → 生成 `Builds/QuestMirror.apk`

## 安装到头显

```bash
chmod +x ~/vr/scripts/quest_install_mirror_apk.sh
~/vr/scripts/quest_install_mirror_apk.sh
```

或手动：

```bash
adb connect 192.168.0.101:5555   # 你的 Quest IP
adb install -r "C:\File\vr\...\Builds/QuestMirror.apk"
```

## 每次运行

### WSL（T1 → T2 → T3 → T4）

```bash
source ~/vr/scripts/wsl_dds_env.sh
source ~/projects/GR00T-WholeBodyControl/.venv_teleop/bin/activate
export PYTHONPATH=~/projects/GR00T-WholeBodyControl

# T1 / T2 / T3 同 Link 方案 …

# T4 — 注意用这个，不是 run_bridge_unity_win.sh
~/vr/scripts/run_bridge_quest_apk.sh
```

**不要**开 `unity_udp_relay.ps1`（那是给 PC Unity 用的）。

### Quest 头显

1. **应用库** 打开 **quest mirror unity**（不是 teleop APK）
2. 应进入原生 VR（G1 场景 + HUD）
3. 等 T4 发 UDP 后画面/数据更新

### PC

- MuJoCo、deploy 终端照常用，**不用 Link**

## 和 teleop APK 的关系

- **meta_quest_teleop**：T3 读手柄遥操 G1
- **quest mirror unity**：头显里看镜像/校准 UI

两个 App **不能长期同时前台**。常用做法：

1. 演示「头显 VR 镜像」：前台 **QuestMirror APK**，T4 发数据
2. 演示「Quest 遥操 G1」：前台 **teleop APK**，PC 上看 MuJoCo；Unity 可在 PC Editor Play（非 VR）

若必须「一边遥操一边头显 VR」，只能再试 Link，或合并成单个 APK（未做）。

## 故障排查

| 现象 | 处理 |
|------|------|
| APK 里 Waiting UDP | T4 是否 `run_bridge_quest_apk.sh`；Quest IP 是否正确 |
| adb 装不上 | USB 调试 / 同一 WiFi `adb connect IP:5555` |
| 头显没进 VR | Android OpenXR + Meta Quest Support 是否勾选后重打 APK |
