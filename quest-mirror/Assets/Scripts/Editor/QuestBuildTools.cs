#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.XR.Management;
using UnityEngine;

namespace SonicQuestMirror.Editor
{
    /// <summary>
    /// Quest APK build (headset-native VR, no Quest Link).
    /// </summary>
    public static class QuestBuildTools
    {
        private const string ScenePath = "Assets/Scenes/QuestMirrorMain.unity";
        private const string ApkOutput = "Builds/QuestMirror.apk";

        [MenuItem("Sonic Quest Mirror/3) Configure Android (Quest) Build Settings")]
        public static void ConfigureAndroidBuild()
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(
                BuildTargetGroup.Android,
                BuildTarget.Android);
            EditorUserBuildSettings.androidBuildSystem = AndroidBuildSystem.Gradle;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel29;
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;

            var scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            EditorBuildSettings.scenes = scenes;

            var androidXr = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(
                BuildTargetGroup.Android);
            if (androidXr != null)
            {
                androidXr.InitManagerOnStart = true;
                if (androidXr.Manager != null)
                {
                    androidXr.Manager.automaticLoading = true;
                    androidXr.Manager.automaticRunning = true;
                }
            }

            Debug.Log("[QuestMirror] Android build configured. Scene: " + ScenePath);
            EditorUtility.DisplayDialog(
                "Quest Android",
                "Build Target = Android\n" +
                "Scene = QuestMirrorMain\n\n" +
                "Next:\n" +
                "• Edit → Project Settings → XR Plug-in Management → Android → OpenXR\n" +
                "• Add Meta Quest Touch Plus Controller Profile\n" +
                "• Sonic Quest Mirror → 4) Build Quest APK",
                "OK");
        }

        [MenuItem("Sonic Quest Mirror/4) Build Quest APK")]
        public static void BuildQuestApk()
        {
            if (!File.Exists(ScenePath))
            {
                EditorUtility.DisplayDialog(
                    "Missing scene",
                    "Run: Build Everything (Complete — Meshes + Scene) first.",
                    "OK");
                return;
            }

            ConfigureAndroidBuild();

            var dir = Path.GetDirectoryName(ApkOutput);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            var opts = new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = ApkOutput,
                target = BuildTarget.Android,
                options = BuildOptions.None,
            };

            var report = BuildPipeline.BuildPlayer(opts);
            if (report.summary.result == BuildResult.Succeeded)
            {
                Debug.Log("[QuestMirror] APK: " + Path.GetFullPath(ApkOutput));
                EditorUtility.DisplayDialog(
                    "Build OK",
                    "APK:\n" + Path.GetFullPath(ApkOutput) +
                    "\n\n安装（WSL）：\n" +
                    "  ~/vr/scripts/quest_install_mirror_apk.sh\n\n" +
                    "T4（不走 Link）：\n" +
                    "  ~/vr/scripts/run_bridge_quest_apk.sh\n\n" +
                    "头显：应用库打开 quest mirror unity（不是 teleop）。\n" +
                    "PC 不用 Link / relay，MuJoCo 照常。\n\n" +
                    "Note: Mirror 与 teleop 不能同时前台。",
                    "OK");
            }
            else
            {
                EditorUtility.DisplayDialog("Build failed", report.summary.result.ToString(), "OK");
            }
        }
    }
}
#endif
