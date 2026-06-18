using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.UI
{
    /// <summary>
    /// Shows/hides calibration vs teleop visuals based on display_mode from bridge.
    /// </summary>
    public class PipelineModeController : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private GameObject calibrationGroup;
        [SerializeField] private GameObject teleopGroup;
        [SerializeField] private GameObject g1AvatarGroup;
        [SerializeField] private Behaviour errorArrowsView;

        private bool _calibVisible = true;
        private bool _teleopVisible;
        private bool _arrowsEnabled;
        private bool _avatarVisible = true;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();

            if (teleopGroup != null)
            {
                teleopGroup.SetActive(false);
                _teleopVisible = false;
            }

            if (g1AvatarGroup == null)
            {
                var avatar = GameObject.Find("G1Avatar");
                if (avatar != null)
                    g1AvatarGroup = avatar;
            }
            if (g1AvatarGroup != null)
            {
                g1AvatarGroup.SetActive(false);
                _avatarVisible = false;
            }

            FixHudCanvasScale();
        }

        private static void FixHudCanvasScale()
        {
            var canvasGo = GameObject.Find("TeleopHudCanvas");
            if (canvasGo == null)
                return;
            if (canvasGo.transform.localScale.sqrMagnitude < 0.01f)
                canvasGo.transform.localScale = Vector3.one;
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
            if (pkt == null)
                return;

            var calibMode = string.IsNullOrEmpty(pkt.display_mode)
                || pkt.display_mode.ToUpperInvariant() == "CALIBRATION";
            var showCalibVisuals = calibMode || !pkt.calibrated;
            var showTeleop = !calibMode;
            var showArrows = !calibMode && pkt.calibrated;

            if (calibrationGroup != null && showCalibVisuals != _calibVisible)
            {
                calibrationGroup.SetActive(showCalibVisuals);
                _calibVisible = showCalibVisuals;
            }

            if (teleopGroup != null && showTeleop != _teleopVisible)
            {
                teleopGroup.SetActive(showTeleop);
                _teleopVisible = showTeleop;
            }

            if (g1AvatarGroup != null && showTeleop != _avatarVisible)
            {
                g1AvatarGroup.SetActive(showTeleop);
                _avatarVisible = showTeleop;
            }

            if (errorArrowsView != null && showArrows != _arrowsEnabled)
            {
                errorArrowsView.enabled = showArrows;
                _arrowsEnabled = showArrows;
            }
        }
    }
}
