using System.Collections.Generic;
using System.Globalization;
using SonicQuestMirror.Protocol;
using SonicQuestMirror.Robot;

namespace SonicQuestMirror.Robot
{
    /// <summary>
    /// JsonUtility cannot parse dynamic visual_links dict — extract per-link poses from raw JSON.
    /// </summary>
    public static class VisualLinksParser
    {
        public static Dictionary<string, PoseDto> Parse(string json)
        {
            var result = new Dictionary<string, PoseDto>();
            if (string.IsNullOrEmpty(json))
                return result;

            var key = "\"visual_links\"";
            var idx = json.IndexOf(key, System.StringComparison.Ordinal);
            if (idx < 0)
                return result;

            foreach (var link in G1LinkRegistry.LinkNames)
            {
                var pose = TryExtractLinkPose(json, idx, link);
                if (pose != null)
                    result[link] = pose;
            }
            return result;
        }

        public static PoseDto TryExtractLinkPose(string json, int blockStart, string linkName)
        {
            var needle = $"\"{linkName}\"" ;
            var i = json.IndexOf(needle, blockStart, System.StringComparison.Ordinal);
            if (i < 0)
                return null;

            var pIdx = json.IndexOf("\"p\"", i, System.StringComparison.Ordinal);
            var qIdx = json.IndexOf("\"q\"", i, System.StringComparison.Ordinal);
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
            var list = new List<float>(parts.Length);
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
