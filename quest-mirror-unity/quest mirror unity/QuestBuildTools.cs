#if UNITY_EDITOR
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.XR.Management;
using UnityEngine;

namespace SonicQuestMirror.Editor
{
    /// <summary>
    /// Quest Link (PC) + optional Quest APK build.
    /// </summary>
    public static class QuestBuildTools
    {
        private const string ScenePath = "Assets/Scenes/QuestMirrorMain.unity";
        private const string ApkOutput = "Builds/QuestMirror.apk";
        private const string WinExeOutput = "Builds/QuestMirror_Win64/QuestMirror.exe";

        [MenuItem("Sonic Quest Mirror/5) Configure Quest Link (Windows PC)")]
        public static void ConfigureQuestLinkWindows()
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(
                BuildTargetGroup.Standalone,
                BuildTarget.StandaloneWindows64);

            var scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            EditorBuildSettings.scenes = scenes;

            var settings = XRGeneralSettingsPerBuildTarget.XRGeneralSettingsForBuildTarget(
                BuildTargetGroup.Standalone);
            if (settings != null)
                settings.InitManagerOnStart = true;

            PlayerSettings.virtualRealitySupported = true;
            // Mono avoids requiring IL2CPP module in Unity Hub for PC Quest Link builds.
            PlayerSettings.SetScriptingBackend(
                BuildTargetGroup.Standalone,
                ScriptingImplementation.Mono2x);
            // VR on HMD only — PC stays windowed for MuJoCo / other tools.
            PlayerSettings.fullscreenMode = FullScreenMode.Windowed;
            PlayerSettings.defaultScreenWidth = 480;
            PlayerSettings.defaultScreenHeight = 270;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.runInBackground = true;

            Debug.Log("[QuestMirror] Quest Link: Standalone + OpenXR + Mono + windowed PC.");
            EditorUtility.DisplayDialog(
                "Quest Link (PC)",
                "PC 端 Quest Link 只需 OpenXR，不需要「Meta Quest Support」。\n" +
                "（Meta Quest Support 只在 Android 标签里，给 APK 用的。）\n\n" +
                "请确认：\n" +
                "1) Edit → Project Settings → XR Plug-in Management\n" +
                "2) 上方选 Standalone / 电脑 / PC 标签\n" +
                "3) 勾选 OpenXR（Initialize XR on Startup 已开）\n" +
                "4) 左侧点 OpenXR → PC 列表里 Oculus Touch Controller Profile 可开\n" +
                "5) Meta Quest Link 显示 Connected\n" +
                "6) 菜单 6) Build & Run Windows VR\n\n" +
                "PC 窗口会缩小为 480×270，可最小化；VR 只在头显。\n" +
                "若头显只有电脑桌面：必须用 exe，Editor Play 不够。",
                "OK");
        }

        [MenuItem("Sonic Quest Mirror/6) Build && Run Windows VR (Quest Link)")]
        public static void BuildAndRunWindowsVr() =>
            BuildWindowsVr(runAfterBuild: true);

        [MenuItem("Sonic Quest Mirror/6b) Build Windows VR only (show errors)")]
        public static void BuildWindowsVrOnly() =>
            BuildWindowsVr(runAfterBuild: false);

        private static void BuildWindowsVr(bool runAfterBuild)
        {
            if (EditorApplication.isCompiling)
            {
                EditorUtility.DisplayDialog(
                    "Still compiling",
                    "等右下角编译转圈结束，Console 无红字后再 Build。",
                    "OK");
                return;
            }

            if (!File.Exists(ScenePath))
            {
                EditorUtility.DisplayDialog(
                    "Missing scene",
                    "先运行：Sonic Quest Mirror → Build Everything (Complete)",
                    "OK");
                return;
            }

            ConfigureQuestLinkWindows();

            var dir = Path.GetDirectoryName(WinExeOutput);
            if (!string.IsNullOrEmpty(dir) && !Directory.Exists(dir))
                Directory.CreateDirectory(dir);

            var opts = new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = WinExeOutput,
                target = BuildTarget.StandaloneWindows64,
                targetGroup = BuildTargetGroup.Standalone,
                options = runAfterBuild
                    ? BuildOptions.AutoRunPlayer | BuildOptions.Development
                    : BuildOptions.Development,
            };

            var report = BuildPipeline.BuildPlayer(opts);
            if (report.summary.result == BuildResult.Succeeded)
            {
                var fullPath = Path.GetFullPath(WinExeOutput);
                Debug.Log("[QuestMirror] Windows VR exe: " + fullPath);
                EditorUtility.DisplayDialog(
                    runAfterBuild ? "Windows VR 已启动" : "Build OK",
                    (runAfterBuild
                        ? "Link Connected 时头显应进入 3D VR。\n\n"
                        : "Build 成功。Link 连好后双击运行：\n") +
                    "先开 relay + WSL T4，再运行 exe。\n\n" +
                    fullPath,
                    "OK");
                return;
            }

            var details = FormatBuildFailure(report);
            Debug.LogError("[QuestMirror] Build failed:\n" + details);
            EditorUtility.DisplayDialog("Build failed", details, "OK");
        }

        private static string FormatBuildFailure(BuildReport report)
        {
            var sb = new StringBuilder();
            sb.AppendLine("结果: " + report.summary.result);
            sb.AppendLine("平台: " + report.summary.platform);
            sb.AppendLine("错误数: " + report.summary.totalErrors);
            sb.AppendLine();

            var n = 0;
            foreach (var step in report.steps)
            {
                foreach (var msg in step.messages)
                {
                    if (msg.type != LogType.Error && msg.type != LogType.Exception)
                        continue;
                    sb.AppendLine("• " + msg.content);
                    if (++n >= 8)
                    {
                        sb.AppendLine("…（更多见 Console）");
                        return sb.ToString();
                    }
                }
            }

            if (n == 0)
            {
                sb.AppendLine("Console 没有详细错误时常见原因：");
                sb.AppendLine("• Unity Hub 未装「Windows Build Support」模块");
                sb.AppendLine("• Console 仍有 C# 编译红字（先修完）");
                sb.AppendLine("• 未 Build Everything，场景/预制体缺失");
                sb.AppendLine();
                sb.AppendLine("请打开 Window → General → Console，");
                sb.AppendLine("复制最上面红色报错发给我。");
            }

            return sb.ToString();
        }

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

            Debug.Log("[QuestMirror] Android build configured. Scene: " + ScenePath);
            EditorUtility.DisplayDialog(
                "Quest Android",
                "Build Target = Android\n" +
                "Scene = QuestMirrorMain\n\n" +
                "Next:\n" +
                "• Edit → Project Settings → XR Plug-in Management → Android → OpenXR\n" +
                "• Add Meta Quest Touch Plus Controller Profile\n" +
                "• Sonic Quest Mirror → Build Quest APK",
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
                    "\n\nInstall: adb install -r Builds/QuestMirror.apk\n" +
                    "T4 UDP: --udp-host <Quest-IP>\n\n" +
                    "Note: APK 与 meta_quest_teleop 不能同时前台；T3 遥操请用 Quest Link + PC Unity Play。",
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
