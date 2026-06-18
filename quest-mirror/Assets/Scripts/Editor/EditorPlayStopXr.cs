#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using UnityEngine.XR.Management;

namespace SonicQuestMirror.Editor
{
    /// <summary>
    /// Editor Play must never boot OpenXR (Quest Link fights OperatorCameraRig).
    /// </summary>
    [InitializeOnLoad]
    internal static class EditorPlayStopXr
    {
        static EditorPlayStopXr()
        {
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
        }

        private static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.ExitingEditMode)
                DisableStandaloneXrBoot();

            if (state == PlayModeStateChange.EnteredPlayMode)
            {
                EditorApplication.delayCall += StopOpenXrIfRunning;
                EditorApplication.delayCall += StopOpenXrIfRunning;
            }
        }

        private static void DisableStandaloneXrBoot()
        {
            var settings = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(
                BuildTargetGroup.Standalone);
            if (settings == null)
                return;

            settings.InitManagerOnStart = false;
            if (settings.Manager != null)
            {
                settings.Manager.automaticLoading = false;
                settings.Manager.automaticRunning = false;
            }
        }

        private static void StopOpenXrIfRunning()
        {
            XRSettings.enabled = false;

            var settings = XRGeneralSettings.Instance;
            if (settings?.Manager == null)
                return;

            var manager = settings.Manager;
            if (manager.activeLoader == null && !manager.isInitializationComplete)
                return;

            manager.StopSubsystems();
            manager.DeinitializeLoader();
            Debug.Log("[QuestMirror] Editor Play — OpenXR stopped; desktop FPV only.");
        }
    }
}
#endif
