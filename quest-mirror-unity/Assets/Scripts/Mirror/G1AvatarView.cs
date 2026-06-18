using System.Collections.Generic;
using SonicQuestMirror.Network;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;
using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Drives full G1 STL mesh rig from MuJoCo FK visual_links (49 links).
    /// Flat prefab: each link is a direct child; poses are pelvis-frame world FK.
    /// </summary>
    public class G1AvatarView : MonoBehaviour
    {
        [SerializeField] private UdpStateReceiver receiver;
        [SerializeField] private Transform g1AvatarRoot;
        [SerializeField] private bool applyStandingPoseOnStart = true;
        [SerializeField] private float poseSmoothSpeed = 14f;

        private readonly Dictionary<string, Transform> _links = new();
        private readonly Dictionary<string, Vector3> _smoothPos = new();
        private readonly Dictionary<string, Quaternion> _smoothRot = new();
        private readonly HashSet<string> _standingAnchored = new();
        private bool _standingAnchorsReady;
        private int _lastAppliedCount;
        private bool _loggedEmpty;

        private void Awake()
        {
            if (receiver == null)
                receiver = FindObjectOfType<UdpStateReceiver>();
            if (g1AvatarRoot == null)
            {
                var go = GameObject.Find("G1Avatar");
                if (go != null)
                    g1AvatarRoot = go.transform;
            }
            if (g1AvatarRoot != null)
                g1AvatarRoot.localRotation = Quaternion.identity;
            RebuildLinkMap();
        }

        private void Start()
        {
            if (applyStandingPoseOnStart)
                ApplyStandingDefaults();
        }

        public void RebuildLinkMap()
        {
            _links.Clear();
            if (g1AvatarRoot == null)
                return;
            foreach (var t in g1AvatarRoot.GetComponentsInChildren<Transform>(true))
            {
                if (t == g1AvatarRoot)
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
            {
                if (!_loggedEmpty)
                {
                    _loggedEmpty = true;
                    Debug.LogWarning("[G1AvatarView] visual_links empty — check bridge / TCP relay.");
                }
                return;
            }

            _loggedEmpty = false;
            ApplyPoses(poses, snap: false);
        }

        private void ApplyStandingDefaults()
        {
            var asset = Resources.Load<TextAsset>("StandingVisualLinks");
            if (asset == null)
            {
                Debug.LogWarning("[G1AvatarView] Missing Resources/StandingVisualLinks.json");
                return;
            }

            var wrapped = "{\"visual_links\":" + asset.text + "}";
            var poses = VisualLinksParser.Parse(wrapped);
            ApplyPoses(poses, snap: true);
            CacheStandingAnchors(poses);
            Debug.Log($"[G1AvatarView] Standing default pose applied ({poses.Count} links).");
        }

        private void CacheStandingAnchors(Dictionary<string, PoseDto> standingPoses)
        {
            _standingAnchored.Clear();
            foreach (var link in new[]
                     {
                         "pelvis", "pelvis_contour_link", "torso_link", "head_link",
                         "waist_yaw_link", "waist_roll_link", "logo_link",
                         "left_hip_pitch_link", "left_hip_roll_link", "left_hip_yaw_link",
                         "left_knee_link", "left_ankle_pitch_link", "left_ankle_roll_link",
                         "right_hip_pitch_link", "right_hip_roll_link", "right_hip_yaw_link",
                         "right_knee_link", "right_ankle_pitch_link", "right_ankle_roll_link",
                     })
            {
                if (standingPoses.ContainsKey(link))
                    _standingAnchored.Add(link);
            }
            _standingAnchorsReady = _standingAnchored.Count > 0;
        }

        private void ApplyPoses(Dictionary<string, PoseDto> poses, bool snap)
        {
            var dt = snap ? 1f : Mathf.Clamp(Time.deltaTime * poseSmoothSpeed, 0f, 1f);
            var applied = 0;
            foreach (var link in G1LinkRegistry.LinkNames)
            {
                if (_standingAnchorsReady && _standingAnchored.Contains(link))
                    continue;
                if (!poses.TryGetValue(link, out var pose))
                    continue;
                if (!_links.TryGetValue(link, out var t))
                    continue;

                var targetPos = PoseMath.MuJoCoToUnityPosition(pose);
                var targetRot = pose.q != null && pose.q.Length >= 4
                    ? PoseMath.MuJoCoToUnityRotationPoseOnly(pose.q[0], pose.q[1], pose.q[2], pose.q[3])
                    : t.localRotation;

                if (snap || !_smoothPos.ContainsKey(link))
                {
                    _smoothPos[link] = targetPos;
                    _smoothRot[link] = targetRot;
                }
                else
                {
                    _smoothPos[link] = Vector3.Lerp(_smoothPos[link], targetPos, dt);
                    _smoothRot[link] = Quaternion.Slerp(_smoothRot[link], targetRot, dt);
                }

                t.localPosition = _smoothPos[link];
                t.localRotation = _smoothRot[link];
                applied++;
            }

            if (applied != _lastAppliedCount)
            {
                _lastAppliedCount = applied;
                Debug.Log($"[G1AvatarView] Applied {applied}/{G1LinkRegistry.LinkNames.Length} link poses.");
            }
        }
    }
}
