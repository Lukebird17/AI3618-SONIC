using System;
using System.Collections.Generic;
using System.Globalization;
using SonicMujocoVr.Core;

namespace SonicMujocoVr.Robot
{
    public static class G1LinkRegistry
    {
        public static readonly string[] LinkNames =
        {
            "pelvis", "pelvis_contour_link", "torso_link", "head_link",
            "waist_yaw_link", "waist_roll_link", "logo_link",
            "left_hip_pitch_link", "left_hip_roll_link", "left_hip_yaw_link",
            "left_knee_link", "left_ankle_pitch_link", "left_ankle_roll_link",
            "right_hip_pitch_link", "right_hip_roll_link", "right_hip_yaw_link",
            "right_knee_link", "right_ankle_pitch_link", "right_ankle_roll_link",
            "left_shoulder_pitch_link", "left_shoulder_roll_link", "left_shoulder_yaw_link",
            "left_elbow_link", "left_wrist_roll_link", "left_wrist_pitch_link", "left_wrist_yaw_link",
            "left_hand_palm_link", "left_hand_thumb_0_link", "left_hand_thumb_1_link", "left_hand_thumb_2_link",
            "left_hand_index_0_link", "left_hand_index_1_link", "left_hand_middle_0_link", "left_hand_middle_1_link",
            "right_shoulder_pitch_link", "right_shoulder_roll_link", "right_shoulder_yaw_link",
            "right_elbow_link", "right_wrist_roll_link", "right_wrist_pitch_link", "right_wrist_yaw_link",
            "right_hand_palm_link", "right_hand_thumb_0_link", "right_hand_thumb_1_link", "right_hand_thumb_2_link",
            "right_hand_index_0_link", "right_hand_index_1_link", "right_hand_middle_0_link", "right_hand_middle_1_link",
        };

        public const string PrefabPath = "Assets/Robot/G1/G1AvatarFull.prefab";
        public const string LegacyPrefabPath = "../../quest-mirror-unity/quest mirror unity/Assets/Robot/G1/G1AvatarFull.prefab";
    }

    public static class VisualLinksParser
    {
        public static Dictionary<string, PoseDto> Parse(string json)
        {
            var result = new Dictionary<string, PoseDto>();
            if (string.IsNullOrEmpty(json))
                return result;
            var block = json.IndexOf("\"visual_links\"", StringComparison.Ordinal);
            if (block < 0)
                return result;
            foreach (var link in G1LinkRegistry.LinkNames)
            {
                var pose = TryExtractLinkPose(json, block, link);
                if (pose != null)
                    result[link] = pose;
            }
            return result;
        }

        private static PoseDto TryExtractLinkPose(string json, int blockStart, string linkName)
        {
            var needle = $"\"{linkName}\"";
            var i = json.IndexOf(needle, blockStart, StringComparison.Ordinal);
            if (i < 0)
                return null;
            var pIdx = json.IndexOf("\"p\"", i, StringComparison.Ordinal);
            var qIdx = json.IndexOf("\"q\"", i, StringComparison.Ordinal);
            if (pIdx < 0 || qIdx < 0)
                return null;
            if (!TryParseFloatArray(json, pIdx, out var p))
                return null;
            if (!TryParseFloatArray(json, qIdx, out var q))
                return null;
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
            var list = new List<float>();
            foreach (var raw in parts)
            {
                if (float.TryParse(raw.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var v))
                    list.Add(v);
            }
            if (list.Count < 3)
                return false;
            values = list.ToArray();
            return true;
        }
    }
}
