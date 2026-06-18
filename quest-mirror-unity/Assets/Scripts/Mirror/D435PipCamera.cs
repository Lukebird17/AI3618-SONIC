using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;
using UnityEngine.UI;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Chest D435 PiP → RenderTexture on HUD RawImage (never renders to screen).
    /// </summary>
    [DefaultExecutionOrder(110)]
    public class D435PipCamera : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Camera pipCamera;
        [SerializeField] private RawImage pipImage;
        [SerializeField] private int textureWidth = 384;
        [SerializeField] private int textureHeight = 216;
        [SerializeField] private float fieldOfView = 69f;
        [SerializeField] private Vector3 opticalFrameCorrection = new Vector3(180f, 0f, 0f);

        private Transform _pipAnchor;
        private RenderTexture _rt;
        private Vector3 _targetLocalPos;
        private Quaternion _targetLocalRot = Quaternion.identity;
        private bool _hasTarget;
        private int _worldCullingMask = -1;
        [SerializeField] private bool lockStandingPoseOnDesktop = true;

        private bool _useFixedStandingPose;

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

            SetDefaultStandingPose();
            _useFixedStandingPose = lockStandingPoseOnDesktop;
            EnsureCamera();
            EnsureAnchor();
        }

        private void Start()
        {
            if (pipImage == null)
            {
                var texGo = GameObject.Find("D435PipTexture");
                if (texGo != null)
                    pipImage = texGo.GetComponent<RawImage>();
            }

            EnsureCamera();
            if (pipImage != null && _rt != null && pipImage.texture != _rt)
                pipImage.texture = _rt;
            if (pipCamera != null)
                pipCamera.enabled = true;
            ApplyAnchorWorld();
        }

        private void EnsureAnchor()
        {
            if (_pipAnchor != null)
                return;

            var go = new GameObject("D435PipAnchor");
            go.transform.SetParent(transform, false);
            _pipAnchor = go.transform;
            pipCamera.transform.SetParent(_pipAnchor, false);
            pipCamera.transform.localRotation = Quaternion.Euler(opticalFrameCorrection);
        }

        private void EnsureCamera()
        {
            if (pipCamera == null)
            {
                var go = new GameObject("D435PipCamera");
                go.transform.SetParent(transform, false);
                pipCamera = go.AddComponent<Camera>();
            }

            pipCamera.depth = 10f;
            pipCamera.fieldOfView = fieldOfView;
            pipCamera.nearClipPlane = 0.05f;
            pipCamera.farClipPlane = 30f;
            pipCamera.clearFlags = CameraClearFlags.SolidColor;
            pipCamera.backgroundColor = new Color(0.05f, 0.06f, 0.08f, 1f);
            pipCamera.stereoTargetEye = StereoTargetEyeMask.None;
            pipCamera.targetDisplay = 0;

            var uiLayer = LayerMask.NameToLayer("UI");
            _worldCullingMask = uiLayer >= 0
                ? ~(1 << uiLayer)
                : ~0;
            pipCamera.cullingMask = _worldCullingMask;

            if (_rt == null)
            {
                _rt = new RenderTexture(textureWidth, textureHeight, 16);
                pipCamera.targetTexture = _rt;
                if (pipImage != null)
                    pipImage.texture = _rt;
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

        private void OnDestroy()
        {
            if (_rt != null)
                _rt.Release();
        }

        private void HandleJson(string json)
        {
            if (_useFixedStandingPose)
                return;

            var pkt = JsonUtility.FromJson<StatePacket>(json);
            if (pkt?.d435_pose == null || !PoseMath.HasPose(pkt.d435_pose))
                return;

            var pos = PoseMath.MuJoCoToUnityPosition(pkt.d435_pose);
            var rot = PoseMath.MuJoCoToUnityRotationPoseOnly(
                pkt.d435_pose.q[0], pkt.d435_pose.q[1], pkt.d435_pose.q[2], pkt.d435_pose.q[3]);
            if (_hasTarget
                && Vector3.Distance(pos, _targetLocalPos) < 0.002f
                && Quaternion.Angle(rot, _targetLocalRot) < 0.25f)
                return;

            _targetLocalPos = pos;
            _targetLocalRot = rot;
            _hasTarget = true;
        }

        private void SetDefaultStandingPose()
        {
            _targetLocalPos = PoseMath.MuJoCoToUnityPosition(0.0537f, 0.0175f, 0.8239f);
            _targetLocalRot = PoseMath.MuJoCoToUnityRotationPoseOnly(0.915f, 0f, 0.4035f, 0f);
            _hasTarget = true;
        }

        private void LateUpdate()
        {
            if (!_hasTarget || _pipAnchor == null || robotRoot == null)
                return;
            ApplyAnchorWorld();
        }

        private void ApplyAnchorWorld()
        {
            var worldPos = robotRoot.TransformPoint(_targetLocalPos);
            var worldRot = robotRoot.rotation * _targetLocalRot;
            _pipAnchor.SetPositionAndRotation(worldPos, worldRot);
        }
    }
}
