using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Simple torso + arm bones linking MuJoCo actual frames (Path B body rig).
    /// </summary>
    public class MujocoBodyRigView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private LineRenderer leftArmLine;
        [SerializeField] private LineRenderer rightArmLine;
        [SerializeField] private LineRenderer spineLine;

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
            if (pkt?.robot_actual == null || robotRoot == null)
                return;

            var torso = pkt.robot_actual.torso;
            if (!PoseMath.HasPose(torso))
                return;

            var t = World(torso);
            SetLine(spineLine, t, World(pkt.robot_actual.head));
            SetLine(leftArmLine, t, World(pkt.robot_actual.left));
            SetLine(rightArmLine, t, World(pkt.robot_actual.right));
        }

        private Vector3 World(PoseDto pose)
        {
            return robotRoot.TransformPoint(PoseMath.MuJoCoToUnityPosition(pose));
        }

        private static void SetLine(LineRenderer lr, Vector3 a, Vector3 b)
        {
            if (lr == null)
                return;
            lr.positionCount = 2;
            lr.SetPosition(0, a);
            lr.SetPosition(1, b);
            lr.enabled = true;
        }
    }
}
