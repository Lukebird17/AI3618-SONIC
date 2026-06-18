# Quest Mirror（Unity）

## 开哪个工程？

**只开内层完整工程：**

| | 路径 |
|--|------|
| Windows | `C:\File\vr\quest-mirror-unity\quest mirror unity` |
| WSL | `~/vr/quest-mirror-unity/quest mirror unity` |

菜单里应有 **`Build Everything (Complete)`**。  
若只有 **`Setup Scene (Editor UDP Test)`** → 你开错工程了。

详细步骤：**`~/vr/docs/UNITY_SETUP.md`**

WSL 改代码后同步到 Windows：

```bash
~/vr/scripts/sync_unity_to_windows.sh
```

---

## 一键构建（Unity Editor）

**`Sonic Quest Mirror` → `Build Everything (Complete)`**

然后 Play + WSL：

```bash
cd ~/vr/sonic-bridge
WIN_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}')
python -m sonic_bridge.run_bridge --synthetic --udp-host $WIN_IP
```

---

## 本目录 `quest-mirror/` 是什么？

只是 **脚本同步副本**（给 rsync 用），**不要**在 Hub 里当 Unity 工程打开。  
完整工程在 **`quest-mirror-unity/quest mirror unity`**。
