using UnityEngine;
#if UNITY_RENDER_PIPELINE_UNIVERSAL
using UnityEngine.Rendering.Universal;
#endif

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// One-time camera setup: desktop = mono FPV only; Android APK = OpenXR stereo.
    /// </summary>
    [DefaultExecutionOrder(-500)]
    public class MirrorPlayBootstrap : MonoBehaviour
    {
        private static bool _done;

        private void Awake()
        {
            if (_done)
                return;
            _done = true;
            FixHudCanvasScale();
            ConfigureMainCamera();
            DisableExtraScreenCameras();
        }

        private static void FixHudCanvasScale()
        {
            var canvasGo = GameObject.Find("TeleopHudCanvas");
            if (canvasGo == null)
                return;
            if (canvasGo.transform.localScale.sqrMagnitude < 0.01f)
                canvasGo.transform.localScale = Vector3.one;
        }

        private static void ConfigureMainCamera()
        {
            var fpvGo = GameObject.Find("FpvCamera");
            if (fpvGo == null)
                return;

            var cam = fpvGo.GetComponent<Camera>();
            if (cam == null)
                return;

            cam.tag = "MainCamera";
            cam.depth = -100f;

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

        private static void DisableExtraScreenCameras()
        {
#if UNITY_ANDROID && !UNITY_EDITOR
            return;
#endif

            var fpvGo = GameObject.Find("FpvCamera");
            foreach (var cam in FindObjectsOfType<Camera>(true))
            {
                if (cam == null)
                    continue;
                if (fpvGo != null && cam.gameObject == fpvGo)
                    continue;
                if (cam.targetTexture != null)
                    continue;
                cam.enabled = false;
            }
        }
    }
}
