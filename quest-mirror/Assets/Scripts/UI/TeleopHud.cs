using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace SonicQuestMirror.UI
{
    public class TeleopHud : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private TextMeshProUGUI statusText;
        [SerializeField] private Image recIndicator;
        [SerializeField] private float latencyWarnMs = 30f;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
        }

        private void OnEnable()
        {
            if (receiver != null)
                receiver.OnJsonReceived += HandleJson;
        }

        private void OnDisable()
        {
            if (receiver != null)
                receiver.OnJsonReceived -= HandleJson;
        }

        private void HandleJson(string json)
        {
            var pkt = JsonUtility.FromJson<StatePacket>(json);
            if (pkt == null || statusText == null)
                return;

            var modeLabel = string.IsNullOrEmpty(pkt.display_mode) ? "CALIBRATION" : pkt.display_mode;
            var calibMode = modeLabel.ToUpperInvariant() == "CALIBRATION";
            var recLine = pkt.recording
                ? "<color=#FF3333>● REC</color>  Press X to stop"
                : "<color=#888888>○ Idle</color>  Press X to record";

            if (recIndicator != null)
                recIndicator.enabled = pkt.recording;

            string switchHint;
            if (calibMode)
            {
                if (!pkt.calibrated)
                {
                    switchHint = pkt.safe_to_switch
                        ? "<color=#55FF55>Align OK → Trigger calibrate → then Y</color>"
                        : "<color=#FF5555>Move solid hands toward ghost wrists</color>";
                }
                else if (!pkt.safe_to_switch)
                {
                    switchHint = "<color=#FFAA00>Calibrated — fine-tune align, then Y for TELEOP</color>";
                }
                else
                {
                    switchHint = "<color=#55FF55>Ready — press Y for TELEOP mirror</color>";
                }
            }
            else
            {
                switchHint = "<color=#55FF55>MuJoCo mirror teleop</color>  |  D435 PiP  |  Y = calibration";
            }

            var latColor = pkt.latency_ms > latencyWarnMs ? "#FFAA00" : "#FFFFFF";
            var mujoco = pkt.robot_joints != null && pkt.robot_joints.Length > 0
                ? "<color=#55FF55>MuJoCo sync</color>"
                : "<color=#888888>MuJoCo pending</color>";
            var calLine = pkt.calibrated
                ? "<color=#55FF55>Sonic calibrated</color>"
                : "<color=#FF5555>Sonic not calibrated (need trigger)</color>";

            var hand = "";
            if (pkt.hand_state != null)
            {
                hand = $"\nHands: L {pkt.hand_state.left_trigger:F1}  R {pkt.hand_state.right_trigger:F1}" +
                       "  (Trigger=cal  Y=mode  X=rec)";
            }

            statusText.text =
                $"SONIC Quest Mirror\n" +
                $"Mode: <b>{modeLabel}</b>  |  {calLine}  |  {recLine}\n" +
                $"Align {pkt.alignment_score:P0}  |  Lat <color={latColor}>{pkt.latency_ms:F0} ms</color>  |  {mujoco}\n" +
                switchHint + hand;
        }
    }
}
