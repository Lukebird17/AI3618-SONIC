using System.Collections.Generic;
using SonicMujocoVr.Core;
using SonicMujocoVr.Network;
using SonicMujocoVr.Robot;
using UnityEngine;

namespace SonicMujocoVr.World
{
    /// <summary>
    /// Drives entire G1 from MuJoCo visual_links only. Hands = MuJoCo FK, not Quest controllers.
    /// </summary>
    public class MujocoRobotView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform g1Root;
        [SerializeField] private float smoothSpeed = 18f;
        [SerializeField] private bool applyStandingOnStart = true;

        private readonly Dictionary<string, Transform> _links = new();
        private readonly Dictionary<string, Vector3> _pos = new();
        private readonly Dictionary<string, Quaternion> _rot = new();

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (g1Root == null)
            {
                var go = GameObject.Find("G1Avatar");
                if (go != null)
                    g1Root = go.transform;
            }
            RebuildLinkMap();
        }

        private void Start()
        {
            if (applyStandingOnStart)
                ApplyStandingDefaults();
        }

        public void RebuildLinkMap()
        {
            _links.Clear();
            if (g1Root == null)
                return;
            foreach (var t in g1Root.GetComponentsInChildren<Transform>(true))
            {
                if (t == g1Root)
                    continue;
                _links[t.name] = t;
            }
        }

        private void OnEnable()
        {
            if (receiver != null)
                receiver.OnJsonReceived += HandleJson;
        }

        private void OnDisable()
        {
            if (receiver != null)
                receiver.OnJsonReceived -= HandleJson;
        }

        private void HandleJson(string json)
        {
            var poses = VisualLinksParser.Parse(json);
            if (poses.Count == 0)
                return;
            ApplyPoses(poses, snap: false);
        }

        private void ApplyStandingDefaults()
        {
            var asset = Resources.Load<TextAsset>("StandingVisualLinks");
            if (asset == null)
            {
                Debug.LogWarning("[MujocoRobotView] No StandingVisualLinks.json — robot may look empty until T4 sends UDP.");
                return;
            }
            var wrapped = "{\"visual_links\":" + asset.text + "}";
            ApplyPoses(VisualLinksParser.Parse(wrapped), snap: true);
            Debug.Log($"[MujocoRobotView] Standing pose ({_links.Count} link transforms in hierarchy).");
        }

        private void ApplyPoses(Dictionary<string, PoseDto> poses, bool snap)
        {
            if (poses.Count == 0)
                return;
            var k = snap ? 1f : 1f - Mathf.Exp(-smoothSpeed * Time.deltaTime);
            foreach (var kv in poses)
            {
                if (!_links.TryGetValue(kv.Key, out var tr))
                    continue;
                var targetPos = MujocoFrame.ToUnityPosition(kv.Value);
                var targetRot = kv.Value.q != null && kv.Value.q.Length >= 4
                    ? MujocoFrame.ToUnityRotationMesh(kv.Value.q[0], kv.Value.q[1], kv.Value.q[2], kv.Value.q[3])
                    : tr.localRotation;
                if (snap || !_pos.ContainsKey(kv.Key))
                {
                    _pos[kv.Key] = targetPos;
                    _rot[kv.Key] = targetRot;
                }
                else
                {
                    _pos[kv.Key] = Vector3.Lerp(_pos[kv.Key], targetPos, k);
                    _rot[kv.Key] = Quaternion.Slerp(_rot[kv.Key], targetRot, k);
                }
                tr.localPosition = _pos[kv.Key];
                tr.localRotation = _rot[kv.Key];
            }
        }
    }
}
