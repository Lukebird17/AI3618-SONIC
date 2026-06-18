using System.Collections;
using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using UnityEngine;
#if ENABLE_VR || UNITY_XR_MANAGEMENT
using UnityEngine.XR;
#endif

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Quest Link (PC OpenXR): anchor XR view at RobotRoot; desktop uses OperatorCameraRig FK head.
    /// Disabled in Unity Editor — use OperatorCameraRig only (stable PC Play).
    /// </summary>
    public class QuestLinkRig : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform viewAnchor;
        [SerializeField] private Transform fpvCamera;
        [SerializeField] private OperatorCameraRig operatorCameraRig;

        private bool _xrActive;
        private int _xrStableCount;
        private bool _xrCandidate;

        private void Awake()
        {
#if UNITY_EDITOR
            if (operatorCameraRig != null)
                operatorCameraRig.enabled = true;
            enabled = false;
            Debug.Log("[QuestLinkRig] Editor Play — desktop FK camera only (Link/XR off).");
            return;
#endif
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (robotRoot == null)
            {
                var root = GameObject.Find("RobotRoot");
                if (root != null)
                    robotRoot = root.transform;
            }
            if (fpvCamera == null && Camera.main != null)
                fpvCamera = Camera.main.transform;
            if (operatorCameraRig == null)
                operatorCameraRig = FindObjectOfType<OperatorCameraRig>();

            EnsureViewAnchor();
            _xrActive = IsXrDevicePresent();
            ApplyXrLayout(_xrActive);
            StartCoroutine(WatchForXr());
        }

        private IEnumerator WatchForXr()
        {
            while (true)
            {
                var xrNow = IsXrDevicePresent();
                if (xrNow == _xrCandidate)
                    _xrStableCount++;
                else
                {
                    _xrCandidate = xrNow;
                    _xrStableCount = 1;
                }

                // Require ~1.5s stable before switching (avoids Link/Editor flicker).
                if (_xrStableCount >= 3 && xrNow != _xrActive)
                {
                    _xrActive = xrNow;
                    ApplyXrLayout(_xrActive);
                    Debug.Log(_xrActive
                        ? "[QuestLinkRig] Quest Link VR active — HMD drives view."
                        : "[QuestLinkRig] Desktop mode — FK head / PC monitor only.");
                }

                yield return new WaitForSeconds(0.5f);
            }
        }

        private void LateUpdate()
        {
            if (!_xrActive || robotRoot == null || viewAnchor == null)
                return;

            viewAnchor.position = robotRoot.position;
            var yaw = robotRoot.rotation.eulerAngles.y;
            viewAnchor.rotation = Quaternion.Euler(0f, yaw, 0f);
        }

        private void EnsureViewAnchor()
        {
            if (viewAnchor != null)
                return;

            var existing = GameObject.Find("ViewAnchor");
            if (existing != null)
            {
                viewAnchor = existing.transform;
                return;
            }

            var go = new GameObject("ViewAnchor");
            viewAnchor = go.transform;
        }

        private void ApplyXrLayout(bool xr)
        {
            EnsureViewAnchor();
            if (fpvCamera == null)
                return;

            if (xr)
            {
                if (fpvCamera.parent != viewAnchor)
                    fpvCamera.SetParent(viewAnchor, true);
                if (operatorCameraRig != null)
                    operatorCameraRig.enabled = false;
                if (fpvCamera.TryGetComponent<Camera>(out var cam))
                    cam.stereoTargetEye = StereoTargetEyeMask.Both;
            }
            else
            {
                if (fpvCamera.parent == viewAnchor)
                    fpvCamera.SetParent(null, true);
                if (operatorCameraRig != null)
                    operatorCameraRig.enabled = true;
                if (fpvCamera.TryGetComponent<Camera>(out var cam))
                    cam.stereoTargetEye = StereoTargetEyeMask.Both;
            }
        }

        private static bool IsXrDevicePresent()
        {
            return XrQuestLinkBootstrap.IsXrRunning();
        }
    }
}
