# MuJoCo 第一人称 → Quest 头显（不用 Unity）

Unity 镜像方案可以停掉。这条路径是 **MuJoCo 直接渲染** 头部相机，经 HTTP MJPEG 推到 Quest 内置浏览器。

## 是什么 / 不是什么

| 是 | 不是 |
|----|------|
| MuJoCo `fpv` 相机真像素，跟 PC 仿真完全同步 | Unity 里重建的 G1 场景 |
| Quest Browser 全屏看（单目） | 立体 VR（左右眼分开） |
| 低延迟、零 Unity | Quest Link 桌面镜像 |

## 每次运行

```bash
# T1：带 FPV 流（WSL）
~/vr/scripts/run_sim_t1_fpv_quest.sh

# T2 deploy（另开终端，照旧）
source ~/vr/scripts/wsl_dds_env.sh
cd ~/projects/GR00T-WholeBodyControl/gear_sonic_deploy
./deploy.sh sim --input-type zmq_manager

# T3 遥操（另开终端，照旧 — 手柄仍走 SONIC，只是「看」换成 MuJoCo FPV）
python gear_sonic/scripts/pico_manager_thread_server.py \
  --manager --reader quest --quest-ip-address <QUEST_IP>
```

终端会打印：

```text
[MuJoCo FPV] MJPEG http://192.168.x.x:8765/
```

## Quest 头显操作

1. 戴 Quest，连 **同一 WiFi**（与 WSL/PC 同网段）
2. 打开 **Browser**（不是 meta_quest_teleop）
3. 地址栏输入 URL（见下方「PC / Quest 用哪个地址」）
4. 画面出来后 **双击 / 全屏**

## PC / Quest 用哪个地址

| 设备 | 地址 | 说明 |
|------|------|------|
| **PC 本机** | `http://localhost:8765/` | WSL 服务经 localhost 转发，**不要用 192.168.x.x** |
| **Quest** | `http://<PC-WiFi-IP>:8765/` | 如 `192.168.0.103`，需先跑网络脚本 |

实测：Windows 上 `192.168.0.102/103:8765` 会超时，只有 `localhost:8765` 能通；Quest 必须用 PC 的 WiFi IP + 端口转发。

## 防火墙 + 端口转发（Quest 必做；PC 用 WiFi IP 时也要）

T1 跑起来后，在 **Windows 管理员 PowerShell** 执行（路径按你 sync 到 Windows 的实际位置改）：

```powershell
powershell -ExecutionPolicy Bypass -File C:\File\vr\scripts\setup_fpv_quest_network.ps1
```

脚本会：`portproxy 0.0.0.0:8765 → 127.0.0.1:8765` + 放行防火墙，并打印 Quest 该打开的 URL。

仅防火墙（不含 portproxy）不够时，单独脚本：`allow_fpv_firewall.ps1`

WSL 内自测（应 200）：

```bash
curl -I http://127.0.0.1:8765/
```

PC 上自测：

```powershell
curl http://localhost:8765/
curl http://192.168.0.103:8765/   # 跑完 setup 脚本后应 200
```

## 技术细节

- 相机：`<camera name="fpv">` 挂在 `torso_link`（与 G1 头部位姿一致）
- 代码：`gear_sonic/utils/mujoco_sim/fpv_mjpeg_server.py`
- 开关：`run_sim_loop.py --enable-fpv-stream --fpv-port 8765 --fpv-hz 30`

## 若以后要立体 VR

需要 WebXR 或原生 Quest APK 接收视频流；当前仓库 **未实现**。现方案是「最快能看到 MuJoCo 真画面」的折中。
