# Quest Link 方案 A — Unity 画面进头显

PC 跑 Unity + T4，Quest 用 **Link** 看画面；T3 继续用 **teleop APK** 读手柄（不冲突）。

## 一次性配置（Windows Unity）

1. 打开工程：`C:\File\vr\quest-mirror-unity\quest mirror unity`
2. 菜单：**Sonic Quest Mirror → 5) Configure Quest Link (Windows PC)**
3. **Edit → Project Settings → XR Plug-in Management → Standalone (PC)**  
   - 勾选 **OpenXR**
4. **OpenXR → Meta Quest Touch Controller Profile** 启用（可选）
5. 若改过场景脚本：**Sonic Quest Mirror → Build Everything (Complete)** 重建场景（含 `QuestLinkRig`）

## 每次运行

### PC
1. 安装并打开 **Meta Quest Link**（或 Oculus PC app）
2. Quest 连上 Link（USB 或 Air Link）
3. PowerShell：`C:\File\vr\scripts\unity_udp_relay.ps1`
4. Unity **Play**（Game 视图或头显里都能看到）

### WSL
```bash
# T1 MuJoCo
~/vr/scripts/run_sim_t1_wsl.sh

# T2 deploy
cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy && ./deploy.sh sim --input-type zmq_manager

# T3 Quest 遥操
python gear_sonic/scripts/pico_manager_thread_server.py --manager --reader quest --quest-ip-address 192.168.0.101

# T4 → Unity
~/vr/scripts/run_bridge_unity_win.sh
```

### Quest 头显
- **前台**：`com.rail.oculus.teleop`（T3 adb 读手柄）
- **画面**：来自 PC Unity，经 Link 显示在头显里

## 验证 Link 是否生效

Unity Console 应出现：
```
[QuestLinkRig] Quest Link active — HMD drives view.
```

若仍是桌面镜像：
```
[QuestLinkRig] Desktop mirror — MuJoCo FK head drives view.
```

## MuJoCo 小窗黑屏

- 确认 T1 用 `run_sim_t1_wsl.sh`（已设 `DISPLAY=:0`）
- WSL 里：`echo $DISPLAY` 应为 `:0`
- 仍黑屏：在 WSL 装 `mesa-utils` 后重开 T1；或 T1 无窗跑法：
  `python gear_sonic/scripts/run_sim_loop.py --enable-onscreen false`
