using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// MuJoCo-sync first-person camera from deploy feedback FK (Path B).
    /// </summary>
    public class FpvCameraController : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform cameraTransform;
        [SerializeField] private bool smoothFollow = false;
        [SerializeField] private float smoothSpeed = 24f;

        private Vector3 _targetLocalPos;
        private Quaternion _targetLocalRot = Quaternion.identity;
        private bool _hasTarget;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (cameraTransform == null && Camera.main != null)
                cameraTransform = Camera.main.transform;
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

        private void LateUpdate()
        {
            if (!_hasTarget || cameraTransform == null || robotRoot == null)
                return;

            var worldPos = robotRoot.TransformPoint(_targetLocalPos);
            var worldRot = robotRoot.rotation * _targetLocalRot;

            if (smoothFollow)
            {
                cameraTransform.position = Vector3.Lerp(
                    cameraTransform.position, worldPos, Time.deltaTime * smoothSpeed);
                cameraTransform.rotation = Quaternion.Slerp(
                    cameraTransform.rotation, worldRot, Time.deltaTime * smoothSpeed);
            }
            else
            {
                cameraTransform.position = worldPos;
                cameraTransform.rotation = worldRot;
            }
        }

        private void HandleJson(string json)
        {
            var pkt = JsonUtility.FromJson<StatePacket>(json);
            var pose = pkt?.unity_head_pose ?? pkt?.mirror_camera_pose ?? pkt?.camera_pose;
            if (pose == null || !PoseMath.HasPose(pose))
                return;

            _targetLocalPos = PoseMath.MuJoCoToUnityPosition(pose);
            _targetLocalRot = PoseMath.MuJoCoToUnityRotationPoseOnly(
                pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
            _hasTarget = true;
        }
    }
}
