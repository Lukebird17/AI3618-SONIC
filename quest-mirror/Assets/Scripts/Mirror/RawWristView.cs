using System.Collections.Generic;
using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Uncalibrated Quest wrists — full G1 dexterous hand mesh (not a single joint cube).
    /// </summary>
    public class RawWristView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private G1HandMeshRig leftHand;
        [SerializeField] private G1HandMeshRig rightHand;

        private bool _handsVisible = true;

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
            EnsureRigs();
        }

        private void EnsureRigs()
        {
            if (leftHand == null)
            {
                var go = GameObject.Find("RawLeftWrist");
                if (go != null)
                    leftHand = go.GetComponent<G1HandMeshRig>() ?? go.AddComponent<G1HandMeshRig>();
            }
            if (rightHand == null)
            {
                var go = GameObject.Find("RawRightWrist");
                if (go != null)
                    rightHand = go.GetComponent<G1HandMeshRig>() ?? go.AddComponent<G1HandMeshRig>();
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
            if (pkt?.vr_3pt_raw == null)
                return;

            var calib = string.IsNullOrEmpty(pkt.display_mode)
                || pkt.display_mode.ToUpperInvariant() == "CALIBRATION";
            var show = calib || !pkt.calibrated;
            if (leftHand != null && show != _handsVisible)
                leftHand.gameObject.SetActive(show);
            if (rightHand != null && show != _handsVisible)
                rightHand.gameObject.SetActive(show);
            _handsVisible = show;
            if (!show)
                return;

            leftHand?.Apply(robotRoot, pkt.vr_3pt_raw.left, null);
            rightHand?.Apply(robotRoot, pkt.vr_3pt_raw.right, null);
        }
    }
}
