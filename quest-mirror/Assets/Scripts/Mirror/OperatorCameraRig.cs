using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;
#if UNITY_RENDER_PIPELINE_UNIVERSAL
using UnityEngine.Rendering.Universal;
#endif

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// PC mirror: camera position from MuJoCo head FK; rotation from unity_head_pose (HMD yaw only).
    /// </summary>
    [DefaultExecutionOrder(100)]
    public class OperatorCameraRig : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform mirrorCameraTransform;

        private Vector3 _targetLocalPos;
        private Quaternion _targetLocalRot = Quaternion.identity;
        private Quaternion _displayLocalRot = Quaternion.identity;
        private bool _hasTarget;
        [SerializeField] private float rotSmoothSpeed = 10f;
        [SerializeField] private float minRotStepDeg = 0.15f;

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
            if (mirrorCameraTransform == null)
            {
                var fpv = GameObject.Find("FpvCamera");
                if (fpv != null)
                    mirrorCameraTransform = fpv.transform;
            }

            if (mirrorCameraTransform == null)
                return;

            if (mirrorCameraTransform.parent != null)
                mirrorCameraTransform.SetParent(null, true);

            if (mirrorCameraTransform.TryGetComponent<Camera>(out var cam))
            {
                cam.tag = "MainCamera";
                cam.nearClipPlane = 0.05f;
#if UNITY_ANDROID && !UNITY_EDITOR
                cam.stereoTargetEye = StereoTargetEyeMask.Both;
#else
                cam.stereoTargetEye = StereoTargetEyeMask.None;
#endif
#if UNITY_RENDER_PIPELINE_UNIVERSAL
                var urp = cam.GetComponent<UniversalAdditionalCameraData>();
                if (urp == null)
                    urp = cam.gameObject.AddComponent<UniversalAdditionalCameraData>();
#if UNITY_ANDROID && !UNITY_EDITOR
                urp.allowXRRendering = true;
#else
                urp.allowXRRendering = false;
#endif
#endif
            }
        }

        private void Start()
        {
            _targetLocalPos = PoseMath.MuJoCoToUnityPosition(0.0241f, -0.0081f, 0.4028f);
            _targetLocalRot = PoseMath.MuJoCoToUnityRotationPoseOnly(0.9991f, 0.011f, 0.0402f, -0.0002f);
            _displayLocalRot = _targetLocalRot;
            _hasTarget = true;
            ApplyCameraWorld(_displayLocalRot);
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
            if (pkt == null)
                return;

            // Position: always MuJoCo FK head (same source as visual_links body).
            if (pkt.robot_actual?.head != null && PoseMath.HasPose(pkt.robot_actual.head))
                _targetLocalPos = PoseMath.MuJoCoToUnityPosition(pkt.robot_actual.head);

            var viewPose = PickViewRotation(pkt);
            if (viewPose?.q == null || viewPose.q.Length < 4)
                return;

            var rot = PoseMath.MuJoCoToUnityRotationPoseOnly(
                viewPose.q[0], viewPose.q[1], viewPose.q[2], viewPose.q[3]);

            if (_hasTarget)
            {
                var step = Quaternion.Angle(rot, _targetLocalRot);
                if (step < minRotStepDeg)
                    return;
            }

            _targetLocalRot = rot;
            _hasTarget = true;
        }

        private void LateUpdate()
        {
            if (!_hasTarget || mirrorCameraTransform == null || robotRoot == null)
                return;
            _displayLocalRot = Quaternion.Slerp(
                _displayLocalRot,
                _targetLocalRot,
                Time.deltaTime * rotSmoothSpeed);
            ApplyCameraWorld(_displayLocalRot);
        }

        private static PoseDto PickViewRotation(StatePacket pkt)
        {
            if (pkt.unity_head_pose?.q != null && pkt.unity_head_pose.q.Length >= 4)
                return pkt.unity_head_pose;
            return null;
        }

        private void ApplyCameraWorld(Quaternion localRot)
        {
            var worldPos = robotRoot.TransformPoint(_targetLocalPos);
            var worldRot = robotRoot.rotation * localRot;
            mirrorCameraTransform.SetPositionAndRotation(worldPos, worldRot);
        }
    }
}
