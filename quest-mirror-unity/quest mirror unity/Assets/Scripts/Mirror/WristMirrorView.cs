using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Live wrist markers from vr_3pt stream (operator's calibrated hands in robot frame).
    /// </summary>
    public class WristMirrorView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform leftWrist;
        [SerializeField] private Transform rightWrist;
        [SerializeField] private Transform headMarker;

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
            if (pkt?.vr_3pt == null || !pkt.calibrated) return;

            PoseMath.ApplyPoseNoMeshBasis(leftWrist, pkt.vr_3pt.left);
            PoseMath.ApplyPoseNoMeshBasis(rightWrist, pkt.vr_3pt.right);
            if (headMarker != null && pkt.vr_3pt.head != null)
                PoseMath.ApplyPoseNoMeshBasis(headMarker, pkt.vr_3pt.head);
        }
    }
}
