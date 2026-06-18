#if UNITY_EDITOR
using System;
using SonicQuestMirror.Protocol;
using UnityEditor;
using UnityEngine;

namespace SonicQuestMirror.Editor
{
    [Serializable]
    public class MujocoSceneLayoutDto
    {
        public string scene;
        public PoseDto pelvis_world;
        public SceneObjectDto[] objects;
    }

    [Serializable]
    public class SceneObjectDto
    {
        public string name;
        public string kind;
        public float[] pos;
        public float[] size;
        public float[] rgba;
        public float[] fromto;
    }

    /// <summary>
    /// Unity editor environment — floor + table in Unity Y-up coords (no MuJoCo axis swap for props).
    /// </summary>
    public static class MujocoSceneBuilder
    {
        private const string LayoutResource = "MujocoSceneLayout";

        public static MujocoSceneLayoutDto LoadLayout()
        {
            var asset = Resources.Load<TextAsset>(LayoutResource);
            if (asset == null)
            {
                Debug.LogError("[MujocoScene] Missing Resources/MujocoSceneLayout.json — run: python -m sonic_bridge.scene_layout");
                return null;
            }
            return JsonUtility.FromJson<MujocoSceneLayoutDto>(asset.text);
        }

        public static GameObject BuildEnvironment(Transform parent = null)
        {
            var env = new GameObject("Environment");
            if (parent != null)
                env.transform.SetParent(parent, false);

            BuildFloor(env.transform);
            BuildTable(env.transform);

            Debug.Log("[MujocoScene] Built Environment: floor + table (Unity coords, no walls)");
            return env;
        }

        public static void ApplyPelvisToRobotRoot(Transform robotRoot)
        {
            var layout = LoadLayout();
            if (layout?.pelvis_world == null || robotRoot == null)
                return;
            robotRoot.localPosition = PoseMath.MuJoCoToUnityPosition(layout.pelvis_world);
            robotRoot.localRotation = Quaternion.identity;
        }

        private static void BuildFloor(Transform parent)
        {
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "floor";
            floor.transform.SetParent(parent, false);
            floor.transform.localPosition = Vector3.zero;
            floor.transform.localRotation = Quaternion.identity;
            floor.transform.localScale = new Vector3(3f, 1f, 3f);
            ApplyMat(floor, CreateMaterial(new Color(0.28f, 0.3f, 0.34f, 1f)));
        }

        /// <summary>
        /// Table in front of robot (+Z). Top ~0.72m, robot pelvis ~0.79m at origin.
        /// </summary>
        private static void BuildTable(Transform parent)
        {
            var table = new GameObject("Table");
            table.transform.SetParent(parent, false);
            table.transform.localPosition = new Vector3(0f, 0f, 0.85f);

            var wood = CreateMaterial(new Color(0.62f, 0.48f, 0.36f, 1f));
            var legMat = CreateMaterial(new Color(0.45f, 0.34f, 0.26f, 1f));

            const float topY = 0.72f;
            const float topW = 0.9f;
            const float topD = 0.6f;
            const float topH = 0.04f;

            var top = GameObject.CreatePrimitive(PrimitiveType.Cube);
            top.name = "table_top";
            top.transform.SetParent(table.transform, false);
            top.transform.localPosition = new Vector3(0f, topY, 0f);
            top.transform.localScale = new Vector3(topW, topH, topD);
            ApplyMat(top, wood);

            const float legH = topY - topH * 0.5f;
            const float legSize = 0.06f;
            var hx = topW * 0.5f - legSize * 0.6f;
            var hz = topD * 0.5f - legSize * 0.6f;
            var legCenters = new[]
            {
                new Vector3(-hx, legH * 0.5f, -hz),
                new Vector3(hx, legH * 0.5f, -hz),
                new Vector3(-hx, legH * 0.5f, hz),
                new Vector3(hx, legH * 0.5f, hz),
            };

            for (var i = 0; i < legCenters.Length; i++)
            {
                var leg = GameObject.CreatePrimitive(PrimitiveType.Cube);
                leg.name = $"table_leg{i + 1}";
                leg.transform.SetParent(table.transform, false);
                leg.transform.localPosition = legCenters[i];
                leg.transform.localScale = new Vector3(legSize, legH, legSize);
                ApplyMat(leg, legMat);
            }
        }

        private static Material CreateMaterial(Color c)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var mat = new Material(shader);
            mat.color = c;
            if (mat.HasProperty("_BaseColor"))
                mat.SetColor("_BaseColor", c);
            return mat;
        }

        private static void ApplyMat(GameObject go, Material mat)
        {
            var r = go.GetComponent<Renderer>();
            if (r != null)
                r.sharedMaterial = mat;
        }
    }
}
#endif
