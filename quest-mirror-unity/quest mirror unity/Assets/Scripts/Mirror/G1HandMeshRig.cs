using System.Collections.Generic;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;
using UnityEngine;
using UnityEngine.Rendering;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Runtime G1 dexterous hand mesh (palm + fingers), anchored at vr_3pt / g1_ref wrist.
    /// Replaces single cube "joint" markers.
    /// </summary>
    public class G1HandMeshRig : MonoBehaviour
    {
        [SerializeField] private bool isLeft = true;
        [SerializeField] private Color tint = Color.white;
        [SerializeField] [Range(0.05f, 1f)] private float alpha = 1f;
        [SerializeField] private GameObject meshSourcePrefab;
        [SerializeField] private float poseSmoothSpeed = 14f;

        private readonly Dictionary<string, Transform> _parts = new();
        private bool _built;
        private Vector3 _smoothPos;
        private Quaternion _smoothRot = Quaternion.identity;
        private bool _hasSmooth;

        public void Configure(bool left, Color color, float opacity, GameObject prefab)
        {
            isLeft = left;
            tint = color;
            alpha = opacity;
            meshSourcePrefab = prefab;
        }

        private void Start()
        {
            BuildIfNeeded();
        }

        public void BuildIfNeeded()
        {
            if (_built)
                return;
            _built = true;
            _parts.Clear();

            if (meshSourcePrefab == null)
            {
                var avatar = GameObject.Find("G1Avatar");
                if (avatar != null)
                    meshSourcePrefab = avatar;
            }

            var partNames = isLeft ? G1LinkRegistry.LeftHandMeshParts : G1LinkRegistry.RightHandMeshParts;
            var copied = 0;

            foreach (var partName in partNames)
            {
                if (_parts.ContainsKey(partName))
                    continue;

                Transform src = null;
                if (meshSourcePrefab != null)
                    src = FindDeepChild(meshSourcePrefab.transform, partName);

                var go = new GameObject(partName);
                go.transform.SetParent(transform, false);
                var hasMesh = false;

                if (src != null)
                {
                    var srcMf = src.GetComponent<MeshFilter>();
                    if (srcMf != null && srcMf.sharedMesh != null)
                    {
                        var mf = go.AddComponent<MeshFilter>();
                        mf.sharedMesh = srcMf.sharedMesh;
                        var mr = go.AddComponent<MeshRenderer>();
                        mr.sharedMaterial = NewColoredMaterial(tint, alpha);
                        mr.shadowCastingMode = ShadowCastingMode.Off;
                        mr.receiveShadows = false;
                        hasMesh = true;
                        copied++;
                    }
                }

                _parts[partName] = go.transform;
            }

            if (copied == 0)
            {
                Debug.LogWarning($"[G1HandMeshRig] No meshes for {(isLeft ? "left" : "right")} hand — run Build Everything.");
                var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cube.transform.SetParent(transform, false);
                cube.transform.localScale = Vector3.one * 0.06f;
                var r = cube.GetComponent<Renderer>();
                if (r != null)
                    r.sharedMaterial = NewColoredMaterial(tint, alpha);
            }
        }

        public void Apply(Transform robotRoot, PoseDto wristPose, Dictionary<string, PoseDto> handParts)
        {
            BuildIfNeeded();
            if (!PoseMath.HasPose(wristPose))
                return;

            if (robotRoot != null && transform.parent != robotRoot)
                transform.SetParent(robotRoot, false);

            var targetPos = PoseMath.MuJoCoToUnityPosition(wristPose);
            var targetRot = PoseMath.MuJoCoToUnityRotationPoseOnly(
                wristPose.q[0], wristPose.q[1], wristPose.q[2], wristPose.q[3]);

            if (!_hasSmooth)
            {
                _smoothPos = targetPos;
                _smoothRot = targetRot;
                _hasSmooth = true;
            }
            else
            {
                var t = Mathf.Clamp(Time.deltaTime * poseSmoothSpeed, 0f, 1f);
                _smoothPos = Vector3.Lerp(_smoothPos, targetPos, t);
                _smoothRot = Quaternion.Slerp(_smoothRot, targetRot, t);
            }

            transform.localPosition = _smoothPos;
            transform.localRotation = _smoothRot;

            if (handParts != null)
            {
                foreach (var kv in handParts)
                {
                    if (!_parts.TryGetValue(kv.Key, out var t))
                        continue;
                    PoseMath.ApplyPoseNoMeshBasis(t, kv.Value);
                }
            }

            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                if (r != null)
                    r.enabled = true;
            }
        }

        public void SetTint(Color color, float opacity)
        {
            tint = color;
            alpha = opacity;
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                if (r == null) continue;
                ApplyColor(r, color, opacity);
            }
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

        private static Material NewColoredMaterial(Color color, float opacity)
        {
            color.a = opacity;
            var shader = Shader.Find("Universal Render Pipeline/Lit")
                         ?? Shader.Find("Standard")
                         ?? Shader.Find("Sprites/Default");
            var mat = new Material(shader);
            mat.color = color;
            if (mat.HasProperty("_BaseColor"))
                mat.SetColor("_BaseColor", color);
            if (opacity < 0.99f)
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

        private static void ApplyColor(Renderer r, Color c, float opacity)
        {
            c.a = opacity;
            foreach (var mat in r.materials)
            {
                if (mat.HasProperty("_Color"))
                    mat.color = c;
                if (mat.HasProperty("_BaseColor"))
                    mat.SetColor("_BaseColor", c);
            }
        }
    }
}
