using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Error arrows: MuJoCo actual wrist → command vr_3pt (tracking error).
    /// </summary>
    public class WristErrorArrowView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private LineRenderer leftArrow;
        [SerializeField] private LineRenderer rightArrow;
        [SerializeField] private float minLengthToShow = 0.01f;

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
            if (pkt?.robot_actual == null || pkt.vr_3pt == null || robotRoot == null)
            {
                SetArrow(leftArrow, false);
                SetArrow(rightArrow, false);
                return;
            }

            UpdateArrow(leftArrow, pkt.robot_actual.left, pkt.vr_3pt.left);
            UpdateArrow(rightArrow, pkt.robot_actual.right, pkt.vr_3pt.right);
        }

        private void UpdateArrow(LineRenderer lr, PoseDto from, PoseDto to)
        {
            if (lr == null || !PoseMath.HasPose(from) || !PoseMath.HasPose(to))
            {
                SetArrow(lr, false);
                return;
            }

            var a = robotRoot.TransformPoint(new Vector3(from.p[0], from.p[1], from.p[2]));
            var b = robotRoot.TransformPoint(new Vector3(to.p[0], to.p[1], to.p[2]));
            if ((b - a).magnitude < minLengthToShow)
            {
                SetArrow(lr, false);
                return;
            }

            lr.positionCount = 2;
            lr.SetPosition(0, a);
            lr.SetPosition(1, b);
            lr.enabled = true;
        }

        private static void SetArrow(LineRenderer lr, bool on)
        {
            if (lr != null)
                lr.enabled = on;
        }
    }
}
