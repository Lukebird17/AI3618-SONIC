using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Calibrated command wrists (vr_3pt) — TELEOP only.
    /// </summary>
    public class CommandWristView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform leftWrist;
        [SerializeField] private Transform rightWrist;

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
            if (pkt?.vr_3pt == null)
            {
                SetVisible(false);
                return;
            }

            var teleop = !string.IsNullOrEmpty(pkt.display_mode)
                && pkt.display_mode.ToUpperInvariant() == "TELEOP";
            // TELEOP: G1 mesh avatar shows wrists + dexterous fingers; hide colored proxy meshes.
            var show = false;
            SetVisible(show);
            if (!show)
                return;

            Apply(leftWrist, pkt.vr_3pt.left);
            Apply(rightWrist, pkt.vr_3pt.right);
        }

        private void SetVisible(bool visible)
        {
            if (leftWrist != null)
                leftWrist.gameObject.SetActive(visible);
            if (rightWrist != null)
                rightWrist.gameObject.SetActive(visible);
        }

        private void Apply(Transform target, PoseDto pose)
        {
            if (target == null || !PoseMath.HasPose(pose))
                return;
            if (robotRoot != null)
                target.SetParent(robotRoot, false);
            PoseMath.ApplyPoseNoMeshBasis(target, pose);
        }
    }
}
