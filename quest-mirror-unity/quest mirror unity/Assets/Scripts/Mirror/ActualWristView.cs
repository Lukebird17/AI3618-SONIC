using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// MuJoCo measured wrists — dexterous hand mesh during calibration (hidden in TELEOP; G1Avatar shows sim).
    /// </summary>
    public class ActualWristView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private G1HandMeshRig leftActual;
        [SerializeField] private G1HandMeshRig rightActual;
        [SerializeField] private Transform torsoMarker;

        private bool _handsVisible = true;
        private bool _torsoVisible = true;

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
            if (leftActual == null)
            {
                var go = GameObject.Find("ActualLeftWrist");
                if (go != null)
                    leftActual = go.GetComponent<G1HandMeshRig>() ?? go.AddComponent<G1HandMeshRig>();
            }
            if (rightActual == null)
            {
                var go = GameObject.Find("ActualRightWrist");
                if (go != null)
                    rightActual = go.GetComponent<G1HandMeshRig>() ?? go.AddComponent<G1HandMeshRig>();
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
            if (pkt?.robot_actual == null)
                return;

            var teleop = !string.IsNullOrEmpty(pkt.display_mode)
                && pkt.display_mode.ToUpperInvariant() == "TELEOP";
            // G1Avatar already renders measured wrists — only optional torso marker in calibration.
            SetHandsVisible(false);
            SetTorsoVisible(!teleop);
            if (teleop || torsoMarker == null || !PoseMath.HasPose(pkt.robot_actual.torso))
                return;

            if (robotRoot != null)
                torsoMarker.SetParent(robotRoot, false);
            PoseMath.ApplyPoseNoMeshBasis(torsoMarker, pkt.robot_actual.torso);
        }

        private void SetHandsVisible(bool visible)
        {
            if (visible == _handsVisible)
                return;
            _handsVisible = visible;
            if (leftActual != null)
                leftActual.gameObject.SetActive(visible);
            if (rightActual != null)
                rightActual.gameObject.SetActive(visible);
        }

        private void SetTorsoVisible(bool visible)
        {
            if (visible == _torsoVisible)
                return;
            _torsoVisible = visible;
            if (torsoMarker != null)
                torsoMarker.gameObject.SetActive(visible);
        }
    }
}
