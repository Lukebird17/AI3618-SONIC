#if UNITY_EDITOR
using UnityEditor;
using UnityEditor.XR.Management;
using UnityEngine;

namespace SonicQuestMirror.Editor
{
    public static class MirrorPlaySettingsMenu
    {
        [MenuItem("Sonic Quest Mirror/Fix PC Play (disable Standalone OpenXR)")]
        public static void DisableStandaloneOpenXr()
        {
            var settings = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(
                BuildTargetGroup.Standalone);
            if (settings != null)
            {
                settings.InitManagerOnStart = false;
                if (settings.Manager != null)
                {
                    settings.Manager.automaticLoading = false;
                    settings.Manager.automaticRunning = false;
                }
            }

            EditorUtility.DisplayDialog(
                "PC Play 设置",
                "已关闭 Standalone 的 OpenXR 自动启动。\n\n" +
                "请确认：Project Settings → XR Plug-in Management → Standalone\n" +
                "取消勾选 OpenXR（若仍闪）。\n\n" +
                "然后菜单 Build Everything 重建场景，再 Play。",
                "OK");
        }
    }
}
#endif
