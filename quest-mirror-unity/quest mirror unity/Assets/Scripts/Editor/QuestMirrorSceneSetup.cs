#if UNITY_EDITOR
using System;
using SonicQuestMirror.Calibration;
using SonicQuestMirror.Mirror;
using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;
using SonicQuestMirror.UI;
using TMPro;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

namespace SonicQuestMirror.Editor
{
    [Serializable]
    public class HandProxyPartDto
    {
        public string name;
        public float[] p;
        public float[] q;
    }

    [Serializable]
    public class HandProxyLayoutDto
    {
        public string leftAnchor;
        public HandProxyPartDto[] leftParts;
        public string rightAnchor;
        public HandProxyPartDto[] rightParts;
    }

    public static class QuestMirrorSceneSetup
    {
        private const string ScenePath = "Assets/Scenes/QuestMirrorMain.unity";

        [MenuItem("Sonic Quest Mirror/Build Everything (Complete — Meshes + Scene)")]
        [MenuItem("Sonic Quest Mirror/Build Everything (Complete)")]
        public static void BuildEverything()
        {
            G1MeshPrefabBuilder.BuildPrefab();
            SetupEditorScene();
            EditorUtility.DisplayDialog(
                "Sonic Quest Mirror",
                "Complete build:\n" +
                "• G1 mesh prefab\n" +
                "• Lab environment\n" +
                "• Hand proxies (palm + fingers)\n\n" +
                "Next: Play + WSL sonic-bridge",
                "OK");
        }

        [MenuItem("Sonic Quest Mirror/2) Build Complete Scene")]
        public static void SetupEditorScene()
        {
            EnsureFolder("Assets/Scenes");
            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

            CreateEnvironment();

            var robotRoot = new GameObject("RobotRoot");
            robotRoot.transform.position = Vector3.zero;
            MujocoSceneBuilder.ApplyPelvisToRobotRoot(robotRoot.transform);

            var viewAnchor = new GameObject("ViewAnchor");
            viewAnchor.transform.position = Vector3.zero;

            var cam = Camera.main;
            if (cam != null)
            {
                cam.name = "FpvCamera";
                cam.transform.SetParent(null, true);
                cam.transform.position = robotRoot.transform.TransformPoint(
                    PoseMath.MuJoCoToUnityPosition(0.024f, -0.008f, 0.403f));
                cam.transform.rotation = Quaternion.identity;
                cam.tag = "MainCamera";
                cam.nearClipPlane = 0.05f;
                cam.fieldOfView = 75f;
                cam.stereoTargetEye = StereoTargetEyeMask.None;
            }

            var calibGroup = new GameObject("CalibrationGroup");
            calibGroup.transform.SetParent(robotRoot.transform, false);
            var teleopGroup = new GameObject("TeleopGroup");
            teleopGroup.transform.SetParent(robotRoot.transform, false);

            var g1Avatar = InstantiateG1Avatar(robotRoot.transform);
            if (g1Avatar == null)
            {
                EditorUtility.DisplayDialog(
                    "Missing G1 Prefab",
                    "Run: Sonic Quest Mirror → Build Everything (Complete)\n\n" +
                    "Or WSL: python3 ~/vr/scripts/export_g1_meshes_to_unity.py",
                    "OK");
                return;
            }

            var network = new GameObject("SonicNetwork");
            var receiver = network.AddComponent<UdpStateReceiver>();

            var g1Prefab = AssetDatabase.LoadAssetAtPath<GameObject>(G1LinkRegistry.PrefabPath);

            var torso = CreateMarker("TorsoActual", new Vector3(0f, 0.9f, 0f), new Color(0.7f, 0.7f, 0.75f), 0.08f);
            var actualLeft = CreateG1HandMesh("ActualLeftWrist", true, new Color(0.2f, 0.85f, 0.95f), 1f, g1Prefab);
            var actualRight = CreateG1HandMesh("ActualRightWrist", false, new Color(0.2f, 0.85f, 0.95f), 1f, g1Prefab);
            var cmdLeft = CreateG1HandMesh("CommandLeftWrist", true, new Color(0.2f, 0.6f, 1f), 1f, g1Prefab);
            var cmdRight = CreateG1HandMesh("CommandRightWrist", false, new Color(1f, 0.4f, 0.2f), 1f, g1Prefab);
            var rawLeft = CreateG1HandMesh("RawLeftWrist", true, new Color(1f, 0.85f, 0.15f), 1f, g1Prefab);
            var rawRight = CreateG1HandMesh("RawRightWrist", false, new Color(1f, 0.55f, 0.1f), 1f, g1Prefab);
            var leftGhost = CreateG1HandMesh("LeftGhost", true, new Color(0.2f, 0.9f, 0.3f), 0.45f, g1Prefab);
            var rightGhost = CreateG1HandMesh("RightGhost", false, new Color(0.2f, 0.9f, 0.3f), 0.45f, g1Prefab);
            leftGhost.transform.SetParent(calibGroup.transform, true);
            rightGhost.transform.SetParent(calibGroup.transform, true);

            var linesRoot = new GameObject("RigLines");
            linesRoot.transform.SetParent(teleopGroup.transform, false);
            var spineLine = CreateLineRenderer(linesRoot.transform, new Color(0.6f, 0.6f, 0.65f));
            var leftArmLine = CreateLineRenderer(linesRoot.transform, new Color(0.2f, 0.85f, 0.95f));
            var rightArmLine = CreateLineRenderer(linesRoot.transform, new Color(0.2f, 0.85f, 0.95f));

            var arrowsRoot = new GameObject("ErrorArrows");
            arrowsRoot.transform.SetParent(teleopGroup.transform, false);
            var leftArrow = CreateLineRenderer(arrowsRoot.transform, new Color(1f, 0.9f, 0.2f), 0.008f);
            var rightArrow = CreateLineRenderer(arrowsRoot.transform, new Color(1f, 0.9f, 0.2f), 0.008f);

            ParentAll(robotRoot.transform, torso, actualLeft, actualRight, cmdLeft, cmdRight, rawLeft, rawRight, calibGroup, teleopGroup, g1Avatar);

            network.AddComponent<GhostCalibrationView>();
            network.AddComponent<RawWristView>();
            network.AddComponent<CommandWristView>();
            network.AddComponent<ActualWristView>();
            var operatorCam = network.AddComponent<OperatorCameraRig>();
            network.AddComponent<MirrorPlayBootstrap>();
            network.AddComponent<D435PipCamera>();
            network.AddComponent<MujocoBodyRigView>();
            var arrows = network.AddComponent<WristErrorArrowView>();
            network.AddComponent<G1AvatarView>();
            network.AddComponent<MujocoRootSync>();
            network.AddComponent<TeleopHud>();
            var pipeline = network.AddComponent<PipelineModeController>();

            var (hudText, recIndicator, pipImage) = CreateHudCanvas();

            WireReferences(
                network, receiver, robotRoot.transform, cam != null ? cam.transform : null,
                torso, actualLeft, actualRight, cmdLeft, cmdRight, rawLeft, rawRight,
                leftGhost, rightGhost,
                spineLine, leftArmLine, rightArmLine, leftArrow, rightArrow, hudText, pipImage);

            WirePipeline(pipeline, calibGroup, teleopGroup, g1Avatar, operatorCam, arrows);
            var avatarView = network.GetComponent<G1AvatarView>();
            SetRef(avatarView, "g1AvatarRoot", g1Avatar.transform);
            SetRef(network.GetComponent<MujocoRootSync>(), "robotRoot", robotRoot.transform);
            SetRef(network.GetComponent<TeleopHud>(), "recIndicator", recIndicator);

            EditorSceneManager.SaveScene(scene, ScenePath);
            AddSceneToBuildSettings(ScenePath);
            Debug.Log("[QuestMirror] Complete scene saved: " + ScenePath);
        }

        private static GameObject InstantiateG1Avatar(Transform parent)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(G1LinkRegistry.PrefabPath);
            if (prefab == null)
                return null;

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            instance.name = "G1Avatar";
            instance.transform.localPosition = Vector3.zero;
            instance.transform.localRotation = Quaternion.identity;
            return instance;
        }

        private static void CreateEnvironment()
        {
            var env = MujocoSceneBuilder.BuildEnvironment();
            if (env == null)
            {
                EditorUtility.DisplayDialog(
                    "Missing scene layout",
                    "Run WSL: python -m sonic_bridge.scene_layout",
                    "OK");
            }
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.55f, 0.58f, 0.62f);
            RenderSettings.fog = false;
        }

        private static void WirePipeline(
            PipelineModeController pipeline,
            GameObject calibGroup,
            GameObject teleopGroup,
            GameObject g1Avatar,
            OperatorCameraRig operatorCam,
            WristErrorArrowView arrows)
        {
            SetRef(pipeline, "calibrationGroup", calibGroup);
            SetRef(pipeline, "teleopGroup", teleopGroup);
            SetRef(pipeline, "g1AvatarGroup", g1Avatar);
            SetRef(pipeline, "errorArrowsView", arrows);
        }

        private static void ParentAll(Transform root, params GameObject[] objects)
        {
            foreach (var go in objects)
                go.transform.SetParent(root, false);
        }

        private static GameObject CreateMarker(string name, Vector3 pos, Color color, float scale = 0.05f)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.localPosition = pos;
            go.transform.localScale = Vector3.one * scale;
            var renderer = go.GetComponent<Renderer>();
            if (renderer != null)
                renderer.sharedMaterial = NewColoredMaterial(color, 1f);
            return go;
        }

        private static Transform FindDeepChild(Transform parent, string childName)
        {
            if (parent.name == childName)
                return parent;
            for (var i = 0; i < parent.childCount; i++)
            {
                var found = FindDeepChild(parent.GetChild(i), childName);
                if (found != null)
                    return found;
            }
            return null;
        }

        private static GameObject CreateG1HandMesh(
            string name,
            bool isLeft,
            Color tint,
            float alpha,
            GameObject meshPrefab)
        {
            var root = new GameObject(name);
            var rig = root.AddComponent<G1HandMeshRig>();
            rig.Configure(isLeft, tint, alpha, meshPrefab);
            return root;
        }

        private static GameObject CreateG1HandProxy(string name, bool isLeft, Color tint, float alpha)
        {
            var fallbackPos = isLeft ? new Vector3(0.22f, 0.25f, 0.45f) : new Vector3(0.22f, -0.25f, 0.45f);
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(G1LinkRegistry.PrefabPath);
            var layoutAsset = Resources.Load<TextAsset>("HandProxyLayout");
            if (prefab == null || layoutAsset == null)
            {
                if (layoutAsset == null)
                    Debug.LogWarning("[QuestMirror] Missing HandProxyLayout.json — run: python -m sonic_bridge.hand_proxy_layout");
                return CreateMarker(name, fallbackPos, tint, 0.08f);
            }

            var layout = JsonUtility.FromJson<HandProxyLayoutDto>(layoutAsset.text);
            var parts = isLeft ? layout.leftParts : layout.rightParts;
            if (parts == null || parts.Length == 0)
                return CreateMarker(name, fallbackPos, tint, 0.08f);

            var root = new GameObject(name);
            root.transform.localPosition = fallbackPos;
            var copied = 0;
            foreach (var part in parts)
            {
                if (part == null || string.IsNullOrEmpty(part.name))
                    continue;
                var src = FindDeepChild(prefab.transform, part.name);
                if (src == null)
                    continue;
                var srcMf = src.GetComponent<MeshFilter>();
                if (srcMf == null || srcMf.sharedMesh == null)
                    continue;

                var go = new GameObject(part.name);
                go.transform.SetParent(root.transform, false);
                var pose = new PoseDto { p = part.p, q = part.q };
                PoseMath.ApplyPose(go.transform, pose);
                var mf = go.AddComponent<MeshFilter>();
                mf.sharedMesh = srcMf.sharedMesh;
                var mr = go.AddComponent<MeshRenderer>();
                mr.sharedMaterial = NewColoredMaterial(tint, alpha);
                mr.shadowCastingMode = ShadowCastingMode.Off;
                mr.receiveShadows = false;
                copied++;
            }

            if (copied == 0)
            {
                UnityEngine.Object.DestroyImmediate(root);
                return CreateMarker(name, fallbackPos, tint, 0.08f);
            }

            return root;
        }

        private static LineRenderer CreateLineRenderer(Transform parent, Color color, float width = 0.004f)
        {
            var go = new GameObject("Line");
            go.transform.SetParent(parent, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.startWidth = width;
            lr.endWidth = width;
            lr.material = NewColoredMaterial(color, 1f);
            lr.startColor = color;
            lr.endColor = color;
            lr.enabled = false;
            return lr;
        }

        private static Material NewColoredMaterial(Color color, float alpha)
        {
            color.a = alpha;
            var shader = Shader.Find("Universal Render Pipeline/Lit")
                         ?? Shader.Find("Standard")
                         ?? Shader.Find("Sprites/Default");
            var mat = new Material(shader);
            mat.color = color;
            if (mat.HasProperty("_BaseColor"))
                mat.SetColor("_BaseColor", color);
            if (alpha < 0.99f)
                SetTransparent(mat);
            return mat;
        }

        private static void SetTransparent(Material mat)
        {
            if (mat.HasProperty("_Surface"))
            {
                mat.SetFloat("_Surface", 1f);
                mat.SetFloat("_Blend", 0f);
            }
            mat.SetOverrideTag("RenderType", "Transparent");
            mat.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha);
            mat.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
            mat.SetInt("_ZWrite", 0);
            mat.renderQueue = (int)RenderQueue.Transparent;
        }

        private static (TextMeshProUGUI statusText, Image recIndicator, RawImage pipImage) CreateHudCanvas()
        {
            var canvasGo = new GameObject("TeleopHudCanvas");
            canvasGo.transform.localScale = Vector3.one;
            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvasGo.AddComponent<CanvasScaler>();
            canvasGo.AddComponent<GraphicRaycaster>();

            var pipGo = new GameObject("D435PipPanel");
            pipGo.transform.SetParent(canvasGo.transform, false);
            var pipBg = pipGo.AddComponent<Image>();
            pipBg.color = new Color(0f, 0f, 0f, 0.65f);
            var pipRect = pipBg.rectTransform;
            pipRect.anchorMin = new Vector2(1f, 0f);
            pipRect.anchorMax = new Vector2(1f, 0f);
            pipRect.pivot = new Vector2(1f, 0f);
            pipRect.anchoredPosition = new Vector2(-16f, 16f);
            pipRect.sizeDelta = new Vector2(400f, 240f);

            var pipTexGo = new GameObject("D435PipTexture");
            pipTexGo.transform.SetParent(pipGo.transform, false);
            var pipImage = pipTexGo.AddComponent<RawImage>();
            pipImage.color = Color.white;
            var pipTexRect = pipImage.rectTransform;
            pipTexRect.anchorMin = Vector2.zero;
            pipTexRect.anchorMax = Vector2.one;
            pipTexRect.offsetMin = new Vector2(4f, 28f);
            pipTexRect.offsetMax = new Vector2(-4f, -4f);

            var pipLabelGo = new GameObject("D435Label");
            pipLabelGo.transform.SetParent(pipGo.transform, false);
            var pipLabel = pipLabelGo.AddComponent<TextMeshProUGUI>();
            pipLabel.fontSize = 16;
            pipLabel.alignment = TextAlignmentOptions.TopLeft;
            pipLabel.color = new Color(0.85f, 0.9f, 0.95f, 1f);
            pipLabel.text = "D435 Chest Cam (MuJoCo FK)";
            var pipLabelRect = pipLabel.rectTransform;
            pipLabelRect.anchorMin = new Vector2(0f, 1f);
            pipLabelRect.anchorMax = new Vector2(1f, 1f);
            pipLabelRect.pivot = new Vector2(0f, 1f);
            pipLabelRect.anchoredPosition = new Vector2(8f, -4f);
            pipLabelRect.sizeDelta = new Vector2(-16f, 24f);

            var recGo = new GameObject("RecIndicator");
            recGo.transform.SetParent(canvasGo.transform, false);
            var recImg = recGo.AddComponent<Image>();
            recImg.color = new Color(1f, 0.15f, 0.15f, 0.9f);
            recImg.enabled = false;
            var recRect = recImg.rectTransform;
            recRect.anchorMin = new Vector2(1f, 1f);
            recRect.anchorMax = new Vector2(1f, 1f);
            recRect.pivot = new Vector2(1f, 1f);
            recRect.anchoredPosition = new Vector2(-24f, -24f);
            recRect.sizeDelta = new Vector2(28f, 28f);

            var textGo = new GameObject("StatusText");
            textGo.transform.SetParent(canvasGo.transform, false);
            var tmp = textGo.AddComponent<TextMeshProUGUI>();
            tmp.fontSize = 24;
            tmp.alignment = TextAlignmentOptions.TopLeft;
            tmp.color = Color.white;
            tmp.text = "SONIC Quest Mirror\nWaiting for UDP 17771...";
            var rect = tmp.rectTransform;
            rect.anchorMin = new Vector2(0f, 1f);
            rect.anchorMax = new Vector2(0f, 1f);
            rect.pivot = new Vector2(0f, 1f);
            rect.anchoredPosition = new Vector2(20f, -20f);
            rect.sizeDelta = new Vector2(900f, 280f);
            return (tmp, recImg, pipImage);
        }

        private static void WireReferences(
            GameObject network,
            UdpStateReceiver receiver,
            Transform robotRoot,
            Transform cameraTransform,
            GameObject torso,
            GameObject actualLeft,
            GameObject actualRight,
            GameObject cmdLeft,
            GameObject cmdRight,
            GameObject rawLeft,
            GameObject rawRight,
            GameObject leftGhost,
            GameObject rightGhost,
            LineRenderer spineLine,
            LineRenderer leftArmLine,
            LineRenderer rightArmLine,
            LineRenderer leftArrow,
            LineRenderer rightArrow,
            TextMeshProUGUI hudText,
            RawImage pipImage)
        {
            var ghost = network.GetComponent<GhostCalibrationView>();
            SetRef(ghost, "receiver", receiver);
            SetRef(ghost, "robotRoot", robotRoot);
            SetRef(ghost, "leftGhost", leftGhost.GetComponent<G1HandMeshRig>());
            SetRef(ghost, "rightGhost", rightGhost.GetComponent<G1HandMeshRig>());

            var cmd = network.GetComponent<CommandWristView>();
            SetRef(cmd, "receiver", receiver);
            SetRef(cmd, "robotRoot", robotRoot);
            SetRef(cmd, "leftWrist", cmdLeft.transform);
            SetRef(cmd, "rightWrist", cmdRight.transform);

            var raw = network.GetComponent<RawWristView>();
            SetRef(raw, "receiver", receiver);
            SetRef(raw, "robotRoot", robotRoot);
            SetRef(raw, "leftHand", rawLeft.GetComponent<G1HandMeshRig>());
            SetRef(raw, "rightHand", rawRight.GetComponent<G1HandMeshRig>());

            var actual = network.GetComponent<ActualWristView>();
            SetRef(actual, "receiver", receiver);
            SetRef(actual, "robotRoot", robotRoot);
            SetRef(actual, "leftActual", actualLeft.GetComponent<G1HandMeshRig>());
            SetRef(actual, "rightActual", actualRight.GetComponent<G1HandMeshRig>());
            SetRef(actual, "torsoMarker", torso.transform);

            var operatorCam = network.GetComponent<OperatorCameraRig>();
            SetRef(operatorCam, "receiver", receiver);
            SetRef(operatorCam, "robotRoot", robotRoot);
            SetRef(operatorCam, "mirrorCameraTransform", cameraTransform);

            var d435 = network.GetComponent<D435PipCamera>();
            SetRef(d435, "receiver", receiver);
            SetRef(d435, "robotRoot", robotRoot);
            SetRef(d435, "pipImage", pipImage);

            var rig = network.GetComponent<MujocoBodyRigView>();
            SetRef(rig, "receiver", receiver);
            SetRef(rig, "robotRoot", robotRoot);
            SetRef(rig, "spineLine", spineLine);
            SetRef(rig, "leftArmLine", leftArmLine);
            SetRef(rig, "rightArmLine", rightArmLine);

            var arrows = network.GetComponent<WristErrorArrowView>();
            SetRef(arrows, "receiver", receiver);
            SetRef(arrows, "robotRoot", robotRoot);
            SetRef(arrows, "leftArrow", leftArrow);
            SetRef(arrows, "rightArrow", rightArrow);

            var hud = network.GetComponent<TeleopHud>();
            SetRef(hud, "receiver", receiver);
            SetRef(hud, "statusText", hudText);
        }

        private static void SetRef(UnityEngine.Object target, string field, UnityEngine.Object value)
        {
            var so = new SerializedObject(target);
            var prop = so.FindProperty(field);
            if (prop == null)
            {
                Debug.LogWarning("[QuestMirror] Missing field: " + field);
                return;
            }
            prop.objectReferenceValue = value;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
                return;
            var parts = path.Split('/');
            var current = parts[0];
            for (var i = 1; i < parts.Length; i++)
            {
                var next = current + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[i]);
                current = next;
            }
        }

        private static void AddSceneToBuildSettings(string scenePath)
        {
            var scenes = EditorBuildSettings.scenes;
            foreach (var s in scenes)
            {
                if (s.path == scenePath)
                    return;
            }
            var list = new EditorBuildSettingsScene[scenes.Length + 1];
            for (var i = 0; i < scenes.Length; i++)
                list[i] = scenes[i];
            list[list.Length - 1] = new EditorBuildSettingsScene(scenePath, true);
            EditorBuildSettings.scenes = list;
        }
    }
}
#endif
