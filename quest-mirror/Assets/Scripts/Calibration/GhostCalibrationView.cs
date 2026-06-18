using SonicQuestMirror.Mirror;
using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;
using UnityEngine;

namespace SonicQuestMirror.Calibration
{
    /// <summary>
    /// G1 reference ghost hands (semi-transparent dexterous mesh) for alignment.
    /// </summary>
    public class GhostCalibrationView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private G1HandMeshRig leftGhost;
        [SerializeField] private G1HandMeshRig rightGhost;
        [SerializeField] private Color safeColor = new Color(0.2f, 0.9f, 0.3f, 0.7f);
        [SerializeField] private Color warnColor = new Color(0.95f, 0.75f, 0.1f, 0.7f);
        [SerializeField] private Color dangerColor = new Color(0.95f, 0.2f, 0.2f, 0.75f);

        private bool _ghostsVisible = true;
        private Color _lastTint = Color.clear;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (robotRoot == null)
            {
                var root = GameObject.Find("RobotRoot");
                if (root != null)
                    robotRoot = root.transform;
            }
            if (leftGhost == null)
            {
                var go = GameObject.Find("LeftGhost");
                if (go != null)
                    leftGhost = go.GetComponent<G1HandMeshRig>() ?? go.AddComponent<G1HandMeshRig>();
            }
            if (rightGhost == null)
            {
                var go = GameObject.Find("RightGhost");
                if (go != null)
                    rightGhost = go.GetComponent<G1HandMeshRig>() ?? go.AddComponent<G1HandMeshRig>();
            }
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
            var leftRef = pkt?.g1_ref?.left;
            var rightRef = pkt?.g1_ref?.right;
            if (!PoseMath.HasPose(leftRef) || !PoseMath.HasPose(rightRef))
                return;

            var calib = string.IsNullOrEmpty(pkt.display_mode)
                || pkt.display_mode.ToUpperInvariant() == "CALIBRATION";
            // Keep ghosts visible until SONIC wrist calibration completes (T3 may already be TELEOP).
            var show = calib || !pkt.calibrated;

            if (leftGhost != null && show != _ghostsVisible)
                leftGhost.gameObject.SetActive(show);
            if (rightGhost != null && show != _ghostsVisible)
                rightGhost.gameObject.SetActive(show);
            _ghostsVisible = show;
            if (!show)
                return;

            leftGhost?.Apply(robotRoot, leftRef, null);
            rightGhost?.Apply(robotRoot, rightRef, null);

            var c = dangerColor;
            if (pkt.safe_to_switch) c = safeColor;
            else if (pkt.alignment_score > 0.5f) c = warnColor;

            if (c != _lastTint)
            {
                leftGhost?.SetTint(c, c.a);
                rightGhost?.SetTint(c, c.a);
                _lastTint = c;
            }
        }
    }
}
