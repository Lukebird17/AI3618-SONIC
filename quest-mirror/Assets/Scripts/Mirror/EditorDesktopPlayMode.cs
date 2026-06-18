using UnityEngine;
#if UNITY_EDITOR
using UnityEngine.XR.Management;
#endif

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Unity Editor Play: desktop-only mirror. Stop OpenXR/Link from hijacking MainCamera.
    /// </summary>
    [DefaultExecutionOrder(-1000)]
    public class EditorDesktopPlayMode : MonoBehaviour
    {
        private void Awake()
        {
#if UNITY_EDITOR
            StopOpenXrInEditor();
            foreach (var link in FindObjectsOfType<QuestLinkRig>(true))
                link.enabled = false;
            foreach (var boot in FindObjectsOfType<XrQuestLinkBootstrap>(true))
                boot.enabled = false;
            Debug.Log("[EditorDesktopPlayMode] Editor Play — OpenXR off, FK camera only.");
#endif
        }

#if UNITY_EDITOR
        private static void StopOpenXrInEditor()
        {
            var settings = XRGeneralSettings.Instance;
            if (settings?.Manager == null)
                return;

            var manager = settings.Manager;
            if (manager.isInitializationComplete)
            {
                manager.StopSubsystems();
                manager.DeinitializeLoader();
            }
        }
#endif
    }
}
