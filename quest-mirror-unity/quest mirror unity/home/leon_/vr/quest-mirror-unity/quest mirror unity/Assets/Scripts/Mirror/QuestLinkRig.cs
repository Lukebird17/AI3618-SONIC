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
    /// </summary>
    public class QuestLinkRig : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform robotRoot;
        [SerializeField] private Transform viewAnchor;
        [SerializeField] private Transform fpvCamera;
        [SerializeField] private OperatorCameraRig operatorCameraRig;

        private bool _xrActive;

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
                if (xrNow != _xrActive)
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

        private void OnEnable()
        {
            if (receiver != null)
                receiver.OnJsonReceived += OnJson;
        }

        private void OnDisable()
        {
            if (receiver != null)
                receiver.OnJsonReceived -= OnJson;
        }

        private void OnJson(string json)
        {
            // Detect XR coming online after Play (Quest Link connected mid-session).
            var xrNow = IsXrDevicePresent();
            if (xrNow != _xrActive)
            {
                _xrActive = xrNow;
                ApplyXrLayout(_xrActive);
                Debug.Log(_xrActive
                    ? "[QuestLinkRig] Quest Link active — HMD drives view."
                    : "[QuestLinkRig] Desktop mirror — MuJoCo FK head drives view.");
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
                Debug.Log(
                    "[QuestLinkRig] VR mode: HMD stereo on. " +
                    "If headset still shows PC desktop, OpenXR did not take over — use menu 6) Build & Run Windows VR.");
            }
            else
            {
                if (operatorCameraRig != null)
                    operatorCameraRig.enabled = true;
                Debug.Log(
                    "[QuestLinkRig] Desktop mode: Game view only. " +
                    "Link desktop mirror is NOT immersive VR — build & run Windows exe (menu 6).");
            }
        }

        private static bool IsXrDevicePresent()
        {
            return XrQuestLinkBootstrap.IsXrRunning();
        }
    }
}
