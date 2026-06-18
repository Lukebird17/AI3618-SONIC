using SonicMujocoVr.Core;
using SonicMujocoVr.Network;
using UnityEngine;

namespace SonicMujocoVr.World
{
    /// <summary>RobotRoot: pelvis_world translation only (no rotation).</summary>
    public class MujocoWorldRoot : MonoBehaviour
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
            var pelvis = MujocoFrame.ParsePose(json, "pelvis_world");
            if (!MujocoFrame.HasPose(pelvis))
                return;
            robotRoot.localPosition = MujocoFrame.ToUnityPosition(pelvis);
            robotRoot.localRotation = Quaternion.identity;
        }
    }
}
