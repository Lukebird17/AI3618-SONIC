#if UNITY_EDITOR
using UnityEditor;
using UnityEngine.XR.Management;

namespace SonicQuestMirror.Editor
{
    /// <summary>
    /// Prevent Quest Link OpenXR from taking MainCamera during Editor Play.
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
            if (state != PlayModeStateChange.EnteredPlayMode)
                return;

            var settings = XRGeneralSettings.Instance;
            if (settings?.Manager == null)
                return;

            var manager = settings.Manager;
            if (!manager.isInitializationComplete && manager.activeLoader == null)
                return;

            manager.StopSubsystems();
            manager.DeinitializeLoader();
            UnityEngine.Debug.Log("[QuestMirror] Editor Play — stopped OpenXR loader (desktop mirror mode).");
        }
    }
}
#endif
