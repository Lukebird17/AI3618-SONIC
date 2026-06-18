using System.Collections;
using System.Collections.Generic;
using UnityEngine;
#if ENABLE_VR || UNITY_XR_MANAGEMENT
using UnityEngine.XR;
using UnityEngine.XR.Management;
#endif

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Ensures OpenXR starts when Quest Link is connected (exe may launch before Link is ready).
    /// </summary>
    public class XrQuestLinkBootstrap : MonoBehaviour
    {
        [SerializeField] private float retrySeconds = 45f;

        private void Start()
        {
            StartCoroutine(Bootstrap());
        }

        private IEnumerator Bootstrap()
        {
#if ENABLE_VR || UNITY_XR_MANAGEMENT
            Debug.Log("[XR] Waiting for OpenXR / Quest Link…");
            var deadline = Time.realtimeSinceStartup + retrySeconds;
            while (Time.realtimeSinceStartup < deadline)
            {
                yield return TryEnsureXrRunning();
                if (IsXrRunning())
                {
                    Debug.Log("[XR] VR active — device: " + XRSettings.loadedDeviceName);
                    PcVrDisplayMode.ReleasePcMonitor();
                    yield break;
                }

                yield return new WaitForSeconds(1f);
            }

            Debug.LogError(
                "[XR] OpenXR did NOT start. Headset will only mirror PC desktop.\n" +
                "Fix: 1) Meta Quest Link Connected BEFORE launching exe\n" +
                "2) Project Settings → XR → PC → OpenXR checked\n" +
                "3) Close SteamVR / other OpenXR runtimes\n" +
                "4) Log: %USERPROFILE%\\AppData\\LocalLow\\DefaultCompany\\quest mirror unity\\Player.log");
#else
            Debug.LogWarning("[XR] VR scripting defines missing — build with VR modules.");
            yield break;
#endif
        }

        public static bool IsXrRunning()
        {
#if ENABLE_VR || UNITY_XR_MANAGEMENT
            if (XRSettings.isDeviceActive)
                return true;

            var displays = new List<XRDisplaySubsystem>();
            SubsystemManager.GetSubsystems(displays);
            foreach (var display in displays)
            {
                if (display != null && display.running)
                    return true;
            }
#endif
            return false;
        }

#if ENABLE_VR || UNITY_XR_MANAGEMENT
        private static IEnumerator TryEnsureXrRunning()
        {
            if (IsXrRunning())
                yield break;

            var settings = XRGeneralSettings.Instance;
            if (settings == null || settings.Manager == null)
                yield break;

            var manager = settings.Manager;
            if (!manager.isInitializationComplete)
                yield return manager.InitializeLoader();

            if (manager.activeLoader == null)
                yield break;

            if (!manager.isInitializationComplete)
                yield break;

            manager.StartSubsystems();
        }
#endif
    }
}
