using System.Collections;
using System.Collections.Generic;
using UnityEngine;
#if UNITY_EDITOR
using UnityEngine.Rendering.Universal;
using UnityEngine.XR;
using UnityEngine.XR.Management;
#endif

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Editor Play: single desktop FPV driver. Kills OpenXR/Link and disables extra full-screen cameras.
    /// </summary>
    public static class DesktopMirrorCameraLock
    {
#if UNITY_EDITOR
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void BeforeSceneLoad()
        {
            StopOpenXrImmediate();
            DisableStandaloneXrAutoBoot();
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void AfterSceneLoad()
        {
            var host = new GameObject("[DesktopMirrorCameraLock]");
            host.hideFlags = HideFlags.HideAndDontSave;
            Object.DontDestroyOnLoad(host);
            host.AddComponent<Runner>();
        }

        private sealed class Runner : MonoBehaviour
        {
            private Camera _fpv;
            private bool _logged;

            private void Awake()
            {
                ApplyLock();
            }

            private void Start()
            {
                StartCoroutine(GuardLoop());
            }

            private void LateUpdate()
            {
                ApplyLock();
            }

            private IEnumerator GuardLoop()
            {
                for (var i = 0; i < 240; i++)
                {
                    ApplyLock();
                    yield return new WaitForSeconds(0.25f);
                }
            }

            private void ApplyLock()
            {
                StopOpenXrImmediate();
                DisableLinkScripts();
                BindAndLockFpv();
                DisableExtraScreenCameras();
                StopXrSubsystems();

                if (!_logged && _fpv != null)
                {
                    _logged = true;
                    Debug.Log("[DesktopMirrorCameraLock] Editor desktop FPV locked (Spectator/off, OpenXR off).");
                }
            }

            private void BindAndLockFpv()
            {
                var fpvGo = GameObject.Find("FpvCamera");
                _fpv = fpvGo != null ? fpvGo.GetComponent<Camera>() : Camera.main;
                if (_fpv == null)
                    return;

                if (_fpv.transform.parent != null)
                    _fpv.transform.SetParent(null, true);

                _fpv.tag = "MainCamera";
                _fpv.stereoTargetEye = StereoTargetEyeMask.None;
                _fpv.depth = -10f;
                if (_fpv.TryGetComponent<UniversalAdditionalCameraData>(out var urp))
                    urp.allowXRRendering = false;

                foreach (var rig in FindObjectsOfType<OperatorCameraRig>(true))
                    rig.enabled = true;
            }

            private static void DisableExtraScreenCameras()
            {
                var fpvGo = GameObject.Find("FpvCamera");
                foreach (var cam in FindObjectsOfType<Camera>(true))
                {
                    if (cam == null)
                        continue;

                    if (fpvGo != null && cam.gameObject == fpvGo)
                        continue;

                    // PiP / off-screen RT cameras keep rendering.
                    if (cam.targetTexture != null)
                        continue;

                    if (cam.CompareTag("MainCamera"))
                        cam.tag = "Untagged";

                    cam.stereoTargetEye = StereoTargetEyeMask.None;
                    if (cam.enabled && cam.gameObject.name == "SpectatorCamera")
                        cam.enabled = false;

                    if (cam.TryGetComponent<UniversalAdditionalCameraData>(out var urp))
                        urp.allowXRRendering = false;
                }

                var spectator = GameObject.Find("SpectatorCamera");
                if (spectator != null && spectator.activeSelf)
                    spectator.SetActive(false);
            }

            private static void DisableLinkScripts()
            {
                foreach (var link in FindObjectsOfType<QuestLinkRig>(true))
                    link.enabled = false;
                foreach (var boot in FindObjectsOfType<XrQuestLinkBootstrap>(true))
                    boot.enabled = false;
                foreach (var legacy in FindObjectsOfType<FpvCameraController>(true))
                    legacy.enabled = false;
            }

            private static void StopOpenXrImmediate()
            {
                XRSettings.enabled = false;

                var settings = XRGeneralSettings.Instance;
                if (settings?.Manager == null)
                    return;

                var manager = settings.Manager;
                if (manager.activeLoader != null || manager.isInitializationComplete)
                {
                    manager.StopSubsystems();
                    manager.DeinitializeLoader();
                }
            }

            private static void StopXrSubsystems()
            {
                var displays = new List<XRDisplaySubsystem>();
                SubsystemManager.GetSubsystems(displays);
                foreach (var display in displays)
                {
                    if (display != null && display.running)
                        display.Stop();
                }
            }

            private static void DisableStandaloneXrAutoBoot()
            {
                var settings = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(
                    BuildTargetGroup.Standalone);
                if (settings == null)
                    return;

                settings.InitManagerOnStart = false;
                if (settings.Manager == null)
                    return;

                settings.Manager.automaticLoading = false;
                settings.Manager.automaticRunning = false;
            }
        }
#endif
    }
}
