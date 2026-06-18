using SonicMujocoVr.Core;
using SonicMujocoVr.Network;
using UnityEngine;

namespace SonicMujocoVr.Camera
{
    /// <summary>
    /// Operator view: full 6DOF from hmd_view_pose (MuJoCo pelvis frame).
    /// Fallback: unity_head_pose (legacy yaw-only) then robot_actual.head position.
    /// </summary>
    public class HmdViewCamera : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform cameraTransform;
        [SerializeField] private float smoothSpeed = 20f;

        private Vector3 _pos;
        private Quaternion _rot;
        private bool _init;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (cameraTransform == null)
            {
                var cam = UnityEngine.Camera.main;
                if (cam != null)
                    cameraTransform = cam.transform;
            }
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
            if (cameraTransform == null || robotRoot == null)
                return;

            var hmd = MujocoFrame.ParsePose(json, "hmd_view_pose");
            if (!MujocoFrame.HasPose(hmd))
                hmd = MujocoFrame.ParsePose(json, "unity_head_pose");
            if (!MujocoFrame.HasPose(hmd))
                return;

            var localPos = MujocoFrame.ToUnityPosition(hmd);
            var localRot = hmd.q != null && hmd.q.Length >= 4
                ? MujocoFrame.ToUnityRotationPose(hmd.q[0], hmd.q[1], hmd.q[2], hmd.q[3])
                : Quaternion.identity;

            var worldPos = robotRoot.TransformPoint(localPos);
            var worldRot = robotRoot.rotation * localRot;

            if (!_init)
            {
                _pos = worldPos;
                _rot = worldRot;
                _init = true;
            }
            else
            {
                var t = 1f - Mathf.Exp(-smoothSpeed * Time.deltaTime);
                _pos = Vector3.Lerp(_pos, worldPos, t);
                _rot = Quaternion.Slerp(_rot, worldRot, t);
            }

            cameraTransform.SetPositionAndRotation(_pos, _rot);
        }
    }
}
