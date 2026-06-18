using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Places RobotRoot at MuJoCo pelvis world pose (converted to Unity Y-up).
    /// </summary>
    public class MujocoRootSync : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (robotRoot == null)
            {
                var go = GameObject.Find("RobotRoot");
                if (go != null)
                    robotRoot = go.transform;
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
            if (robotRoot == null)
                return;
            var pkt = JsonUtility.FromJson<StatePacket>(json);
            if (pkt?.pelvis_world == null || !PoseMath.HasPose(pkt.pelvis_world))
                return;

            // Pelvis world offset only; link poses already include MuJoCo→Unity frame fix.
            robotRoot.localPosition = PoseMath.MuJoCoToUnityPosition(pkt.pelvis_world);
            robotRoot.localRotation = Quaternion.identity;
        }
    }
}
