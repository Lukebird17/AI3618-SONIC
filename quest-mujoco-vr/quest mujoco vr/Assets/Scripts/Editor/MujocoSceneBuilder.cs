#if UNITY_EDITOR
using System;
using SonicMujocoVr.Core;
using UnityEditor;
using UnityEngine;

namespace SonicMujocoVr.Editor
{
    [Serializable]
    public class MujocoSceneLayoutDto
    {
        public string scene;
        public PoseDto pelvis_world;
    }

    /// <summary>Quest lab floor + table (matches old v1 scene).</summary>
    public static class MujocoSceneBuilder
    {
        public static GameObject BuildEnvironment(Transform parent = null)
        {
            var env = new GameObject("Environment");
            if (parent != null)
                env.transform.SetParent(parent, false);

            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "floor";
            floor.transform.SetParent(env.transform, false);
            floor.transform.localScale = new Vector3(3f, 1f, 3f);
            ApplyMat(floor, Mat(new Color(0.28f, 0.3f, 0.34f)));

            var table = new GameObject("Table");
            table.transform.SetParent(env.transform, false);
            table.transform.localPosition = new Vector3(0f, 0f, 0.85f);
            var wood = Mat(new Color(0.62f, 0.48f, 0.36f));
            var top = GameObject.CreatePrimitive(PrimitiveType.Cube);
            top.name = "table_top";
            top.transform.SetParent(table.transform, false);
            top.transform.localPosition = new Vector3(0f, 0.72f, 0f);
            top.transform.localScale = new Vector3(0.9f, 0.04f, 0.6f);
            ApplyMat(top, wood);

            return env;
        }

        public static Vector3 PelvisUnityPosition()
        {
            var asset = Resources.Load<TextAsset>("MujocoSceneLayout");
            if (asset != null)
            {
                var layout = JsonUtility.FromJson<MujocoSceneLayoutDto>(asset.text);
                if (layout?.pelvis_world != null && MujocoFrame.HasPose(layout.pelvis_world))
                    return MujocoFrame.ToUnityPosition(layout.pelvis_world);
            }
            return MujocoFrame.ToUnityPosition(0f, 0f, 0.793f);
        }

        private static Material Mat(Color c)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var mat = new Material(shader) { color = c };
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
