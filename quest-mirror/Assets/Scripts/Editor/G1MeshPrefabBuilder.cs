#if UNITY_EDITOR
using System.IO;
using SonicQuestMirror.Robot;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace SonicQuestMirror.Editor
{
    public static class G1MeshPrefabBuilder
    {
        [MenuItem("Sonic Quest Mirror/1) Import G1 Meshes & Build Prefab")]
        public static void BuildPrefab()
        {
            EnsureFolders();
            var mat = EnsureRobotMaterial();
            var root = new GameObject("G1AvatarFull");
            var built = 0;
            var missing = 0;

            foreach (var link in G1LinkRegistry.LinkNames)
            {
                var mesh = LoadMesh(link);
                if (mesh == null)
                {
                    missing++;
                    Debug.LogWarning($"[G1Import] Missing mesh: {link}. Run WSL export_g1_meshes_to_unity.py first.");
                    continue;
                }

                var linkGo = new GameObject(link);
                linkGo.transform.SetParent(root.transform, false);
                var mf = linkGo.AddComponent<MeshFilter>();
                mf.sharedMesh = mesh;
                var mr = linkGo.AddComponent<MeshRenderer>();
                mr.sharedMaterial = mat;
                mr.shadowCastingMode = ShadowCastingMode.On;
                mr.receiveShadows = true;
                built++;
            }

            var prefabPath = G1LinkRegistry.PrefabPath;
            PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            Object.DestroyImmediate(root);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log($"[G1Import] Prefab saved: {prefabPath} ({built} links, {missing} missing)");
            if (missing > 0)
            {
                EditorUtility.DisplayDialog(
                    "G1 Mesh Import",
                    $"已导入 {built} 个 link，{missing} 个缺失。\n\n" +
                    "在 WSL 运行:\npython3 ~/vr/scripts/export_g1_meshes_to_unity.py\n\n" +
                    "然后重新点本菜单。",
                    "OK");
            }
        }

        private static Mesh LoadMesh(string linkName)
        {
            var objPath = $"{G1LinkRegistry.MeshFolder}/{linkName}.obj";
            if (!File.Exists(objPath))
                return null;

            foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(objPath))
            {
                if (asset is Mesh mesh)
                    return mesh;
            }

            // Force reimport if Unity hasn't parsed OBJ yet
            AssetDatabase.ImportAsset(objPath, ImportAssetOptions.ForceUpdate);
            foreach (var asset in AssetDatabase.LoadAllAssetsAtPath(objPath))
            {
                if (asset is Mesh mesh)
                    return mesh;
            }
            return null;
        }

        private static Material EnsureRobotMaterial()
        {
            var path = G1LinkRegistry.RobotMaterialPath;
            var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing != null)
                return existing;

            EnsureFolders();
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var mat = new Material(shader);
            var color = new Color(0.72f, 0.74f, 0.78f);
            mat.color = color;
            if (mat.HasProperty("_BaseColor"))
                mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Smoothness"))
                mat.SetFloat("_Smoothness", 0.45f);
            if (mat.HasProperty("_Metallic"))
                mat.SetFloat("_Metallic", 0.35f);
            AssetDatabase.CreateAsset(mat, path);
            return mat;
        }

        private static void EnsureFolders()
        {
            if (!AssetDatabase.IsValidFolder("Assets/Robot"))
                AssetDatabase.CreateFolder("Assets", "Robot");
            if (!AssetDatabase.IsValidFolder("Assets/Robot/G1"))
                AssetDatabase.CreateFolder("Assets/Robot", "G1");
            if (!AssetDatabase.IsValidFolder("Assets/Robot/G1/Materials"))
                AssetDatabase.CreateFolder("Assets/Robot/G1", "Materials");
            if (!AssetDatabase.IsValidFolder("Assets/Robot/G1/Meshes"))
                AssetDatabase.CreateFolder("Assets/Robot/G1", "Meshes");
        }
    }
}
#endif
