using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Desktop FPV: MuJoCo FK head (robot_actual.head) in robotRoot world space.
    /// </summary>
    public class OperatorCameraRig : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform mirrorCameraTransform;
        [SerializeField] private float smoothSpeed = 18f;
        [SerializeField] private bool instantFollow = false;

        private Vector3 _targetLocalPos;
        private Quaternion _targetLocalRot = Quaternion.identity;
        private bool _hasTarget;
        private bool _lockedHeadSource;

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
            if (mirrorCameraTransform == null && Camera.main != null)
                mirrorCameraTransform = Camera.main.transform;

            if (mirrorCameraTransform != null)
            {
                // Always drive world pose from robotRoot — never fight ViewAnchor locals.
                if (mirrorCameraTransform.parent != null)
                    mirrorCameraTransform.SetParent(null, true);
            }
        }

        private void Start()
        {
            if (mirrorCameraTransform == null || robotRoot == null)
                return;

            _targetLocalPos = PoseMath.MuJoCoToUnityPosition(0.0241f, -0.0081f, 0.4028f);
            _targetLocalRot = PoseMath.MuJoCoToUnityCameraRotation(0.9991f, 0.011f, 0.0402f, -0.0002f);
            _hasTarget = true;
            ApplyCameraWorld();
            if (mirrorCameraTransform.GetComponent<Camera>() is Camera cam)
                cam.nearClipPlane = 0.05f;
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
            var pose = PickCameraPose(pkt);
            if (pose == null || !PoseMath.HasPose(pose))
                return;

            _targetLocalPos = PoseMath.MuJoCoToUnityPosition(pose);
            _targetLocalRot = PoseMath.MuJoCoToUnityCameraRotation(
                pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
            _hasTarget = true;
        }

        private PoseDto PickCameraPose(StatePacket pkt)
        {
            if (pkt == null)
                return null;

            if (pkt.robot_actual?.head != null && PoseMath.HasPose(pkt.robot_actual.head))
            {
                _lockedHeadSource = true;
                return pkt.robot_actual.head;
            }

            if (_lockedHeadSource)
                return null;

            if (pkt.mirror_camera_pose != null && PoseMath.HasPose(pkt.mirror_camera_pose))
                return pkt.mirror_camera_pose;
            if (pkt.camera_pose != null && PoseMath.HasPose(pkt.camera_pose))
                return pkt.camera_pose;
            return pkt.unity_head_pose;
        }

        private void ApplyCameraWorld()
        {
            if (mirrorCameraTransform == null || robotRoot == null)
                return;

            var worldPos = robotRoot.TransformPoint(_targetLocalPos);
            var worldRot = robotRoot.rotation * _targetLocalRot;
            mirrorCameraTransform.SetPositionAndRotation(worldPos, worldRot);
        }

        private void LateUpdate()
        {
            if (!_hasTarget || mirrorCameraTransform == null || robotRoot == null)
                return;

            if (instantFollow)
            {
                ApplyCameraWorld();
                return;
            }

            var worldPos = robotRoot.TransformPoint(_targetLocalPos);
            var worldRot = robotRoot.rotation * _targetLocalRot;
            mirrorCameraTransform.position = Vector3.Lerp(
                mirrorCameraTransform.position, worldPos, Time.deltaTime * smoothSpeed);
            mirrorCameraTransform.rotation = Quaternion.Slerp(
                mirrorCameraTransform.rotation, worldRot, Time.deltaTime * smoothSpeed);
        }
    }
}
