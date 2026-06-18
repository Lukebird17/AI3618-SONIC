using System;
using UnityEngine;

namespace SonicMujocoVr.Core
{
    [Serializable]
    public class PoseDto
    {
        public float[] p;
        public float[] q;
    }

    [Serializable]
    public class StatePacket
    {
        public string type;
        public double ts;
        public string display_mode;
        public bool calibrated;
        public float alignment_score;
        public bool safe_to_switch;
        public PoseDto hmd_view_pose;
        public PoseDto pelvis_world;
        public PoseDto unity_head_pose;
        public string scene_name;
    }

    /// <summary>
    /// Single MuJoCo (ROS: X fwd, Y left, Z up) → Unity (X right, Y up, Z fwd) transform.
    /// </summary>
    public static class MujocoFrame
    {
        private static readonly Quaternion LinkMeshBasis = Quaternion.Euler(-90f, 0f, 0f);

        public static bool HasPose(PoseDto pose) =>
            pose?.p != null && pose.p.Length >= 3;

        public static Vector3 ToUnityPosition(float x, float y, float z) =>
            new Vector3(-y, z, x);

        public static Vector3 ToUnityPosition(PoseDto pose) =>
            ToUnityPosition(pose.p[0], pose.p[1], pose.p[2]);

        public static Quaternion ToUnityRotationMesh(float w, float x, float y, float z) =>
            SimilarityRotation(w, x, y, z) * LinkMeshBasis;

        public static Quaternion ToUnityRotationPose(float w, float x, float y, float z) =>
            SimilarityRotation(w, x, y, z);

        public static void ApplyLocalPose(Transform target, PoseDto pose, bool meshLink)
        {
            if (!HasPose(pose))
                return;
            target.localPosition = ToUnityPosition(pose);
            if (pose.q != null && pose.q.Length >= 4)
            {
                target.localRotation = meshLink
                    ? ToUnityRotationMesh(pose.q[0], pose.q[1], pose.q[2], pose.q[3])
                    : ToUnityRotationPose(pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
            }
        }

        public static PoseDto ParsePose(string json, string fieldName)
        {
            var key = $"\"{fieldName}\"";
            var idx = json.IndexOf(key, StringComparison.Ordinal);
            if (idx < 0)
                return null;
            var pIdx = json.IndexOf("\"p\"", idx, StringComparison.Ordinal);
            var qIdx = json.IndexOf("\"q\"", idx, StringComparison.Ordinal);
            if (pIdx < 0)
                return null;
            if (!TryParseFloatArray(json, pIdx, out var p))
                return null;
            float[] q = null;
            if (qIdx >= 0)
                TryParseFloatArray(json, qIdx, out q);
            return new PoseDto { p = p, q = q };
        }

        private static bool TryParseFloatArray(string json, int keyIdx, out float[] values)
        {
            values = null;
            var bracket = json.IndexOf('[', keyIdx);
            if (bracket < 0)
                return false;
            var end = json.IndexOf(']', bracket);
            if (end < 0)
                return false;
            var inner = json.Substring(bracket + 1, end - bracket - 1);
            var parts = inner.Split(',');
            var list = new float[parts.Length];
            var n = 0;
            foreach (var raw in parts)
            {
                if (float.TryParse(raw.Trim(), System.Globalization.NumberStyles.Float,
                        System.Globalization.CultureInfo.InvariantCulture, out var v))
                    list[n++] = v;
            }
            if (n < 3)
                return false;
            if (n == list.Length)
            {
                values = list;
                return true;
            }
            values = new float[n];
            Array.Copy(list, values, n);
            return true;
        }

        private static Quaternion SimilarityRotation(float w, float x, float y, float z)
        {
            var q = new Quaternion(x, y, z, w);
            var m = Matrix4x4.Rotate(q);
            var ru = new Matrix4x4(
                new Vector4(-m.m10, m.m20, m.m00, 0f),
                new Vector4(-m.m11, m.m21, m.m01, 0f),
                new Vector4(-m.m12, m.m22, m.m02, 0f),
                new Vector4(0f, 0f, 0f, 1f));
            return ru.rotation;
        }
    }
}
