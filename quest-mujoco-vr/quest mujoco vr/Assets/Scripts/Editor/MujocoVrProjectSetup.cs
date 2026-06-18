#if UNITY_EDITOR
using SonicMujocoVr.Core;
using SonicMujocoVr.Network;
using SonicMujocoVr.Robot;
using SonicMujocoVr.World;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using HmdViewCamera = SonicMujocoVr.Camera.HmdViewCamera;

namespace SonicMujocoVr.Editor
{
    public static class MujocoVrProjectSetup
    {
        private const string ScenePath = "Assets/Scenes/MujocoVrMain.unity";
        private const string PrefabPath = "Assets/Robot/G1/G1AvatarFull.prefab";

        [MenuItem("Sonic MuJoCo VR/0) Build Everything (Meshes + Scene)")]
        public static void BuildEverything()
        {
            CopyMeshesFromOld(silent: false);
            BuildScene();
        }

        [MenuItem("Sonic MuJoCo VR/1) Build Scene (v2)")]
        public static void BuildScene()
        {
            EnsureFolder("Assets/Scenes");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

            var dispatcher = new GameObject("MainThreadDispatcher");
            dispatcher.AddComponent<UnityMainThreadDispatcher>();

            var net = new GameObject("SonicNetwork");
            var receiver = net.AddComponent<UdpStateReceiver>();

            MujocoSceneBuilder.BuildEnvironment();

            var robotRoot = new GameObject("RobotRoot");
            robotRoot.transform.position = MujocoSceneBuilder.PelvisUnityPosition();

            var g1Prefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            Transform g1Root;
            if (g1Prefab != null)
            {
                var g1 = (GameObject)PrefabUtility.InstantiatePrefab(g1Prefab);
                g1.name = "G1Avatar";
                g1.transform.SetParent(robotRoot.transform, false);
                g1Root = g1.transform;
                Debug.Log("[Sonic MuJoCo VR] G1AvatarFull prefab loaded.");
            }
            else
            {
                g1Root = new GameObject("G1Avatar").transform;
                g1Root.SetParent(robotRoot.transform, false);
                Debug.LogError(
                    "[Sonic MuJoCo VR] Missing G1 prefab. Run menu 2) or WSL:\n" +
                    "  ~/vr/scripts/copy_g1_to_unity_v2.sh");
            }

            var cam = UnityEngine.Camera.main;
            if (cam != null)
            {
                cam.gameObject.name = "HmdViewCamera";
                cam.transform.position = robotRoot.transform.TransformPoint(
                    MujocoFrame.ToUnityPosition(0.024f, -0.008f, 0.403f));
                cam.nearClipPlane = 0.05f;
                cam.farClipPlane = 80f;
                cam.gameObject.AddComponent<HmdViewCamera>();
            }

            var worldRoot = robotRoot.AddComponent<MujocoWorldRoot>();
            var robotView = robotRoot.AddComponent<MujocoRobotView>();
            WireRef(robotView, "g1Root", g1Root);
            WireRef(robotView, "receiver", receiver);
            WireRef(worldRoot, "robotRoot", robotRoot.transform);
            WireRef(worldRoot, "receiver", receiver);

            if (cam != null)
            {
                var hmd = cam.GetComponent<HmdViewCamera>();
                WireRef(hmd, "cameraTransform", cam.transform);
                WireRef(hmd, "robotRoot", robotRoot.transform);
                WireRef(hmd, "receiver", receiver);
            }

            EditorSceneManager.SaveScene(scene, ScenePath);
            SetStartupScene(ScenePath);

            var hasMesh = g1Root != null && g1Root.childCount > 0;
            EditorUtility.DisplayDialog(
                "Sonic MuJoCo VR v2",
                (hasMesh
                    ? "Scene OK — G1 mesh + floor + table.\n\nPlay + T4 bridge."
                    : "Scene saved but G1 mesh MISSING.\n\nRun 2) Copy G1 Meshes, then 1) again."),
                "OK");
        }

        [MenuItem("Sonic MuJoCo VR/2) Copy G1 Meshes From Old Project")]
        public static void CopyMeshesFromOldMenu() => CopyMeshesFromOld(silent: false);

        private static void CopyMeshesFromOld(bool silent)
        {
            EnsureFolder("Assets/Robot/G1");

            var copied = 0;
            var srcPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            if (srcPrefab == null)
            {
                var candidates = new[]
                {
                    "Assets/../quest-mirror-unity/quest mirror unity/Assets/Robot/G1/G1AvatarFull.prefab",
                    "../../quest-mirror-unity/quest mirror unity/Assets/Robot/G1/G1AvatarFull.prefab",
                };
                foreach (var rel in candidates)
                {
                    var abs = System.IO.Path.GetFullPath(
                        System.IO.Path.Combine(Application.dataPath, rel));
                    if (!System.IO.File.Exists(abs))
                        continue;
                    var projRel = "Assets/Robot/G1/G1AvatarFull.prefab";
                    System.IO.Directory.CreateDirectory(
                        System.IO.Path.Combine(Application.dataPath, "Robot/G1"));
                    System.IO.File.Copy(abs, System.IO.Path.Combine(Application.dataPath, "Robot/G1/G1AvatarFull.prefab"), true);
                    copied++;
                    break;
                }
            }
            else
            {
                copied = 1;
            }

            AssetDatabase.Refresh();
            if (!silent)
            {
                if (copied > 0)
                    EditorUtility.DisplayDialog("Copy G1", "G1AvatarFull.prefab ready.\nNow run 1) Build Scene.", "OK");
                else
                    EditorUtility.DisplayDialog(
                        "Copy G1",
                        "Copy failed in Unity.\n\nWSL:\n  ~/vr/scripts/copy_g1_to_unity_v2.sh\n  ~/vr/scripts/sync_unity_v2_to_windows.sh",
                        "OK");
            }
        }

        private static void WireRef(Object target, string prop, Object value)
        {
            var so = new SerializedObject(target);
            so.FindProperty(prop).objectReferenceValue = value;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void SetStartupScene(string scenePath)
        {
            var scenes = EditorBuildSettings.scenes;
            var found = false;
            for (var i = 0; i < scenes.Length; i++)
            {
                if (scenes[i].path == scenePath)
                {
                    scenes[i].enabled = true;
                    found = true;
                }
            }
            if (!found)
            {
                var list = new EditorBuildSettingsScene[scenes.Length + 1];
                scenes.CopyTo(list, 0);
                list[scenes.Length] = new EditorBuildSettingsScene(scenePath, true);
                EditorBuildSettings.scenes = list;
            }
            else
            {
                EditorBuildSettings.scenes = scenes;
            }
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
                return;
            var parts = path.Split('/');
            var cur = parts[0];
            for (var i = 1; i < parts.Length; i++)
            {
                var next = cur + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(cur, parts[i]);
                cur = next;
            }
        }
    }
}
#endif
