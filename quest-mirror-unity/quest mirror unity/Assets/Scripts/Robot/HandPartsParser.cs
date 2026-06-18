using System;
using System.Collections.Generic;
using SonicQuestMirror.Protocol;
using UnityEngine;

namespace SonicQuestMirror.Robot
{
    /// <summary>Parse left_hand_display / right_hand_display; fallback to HandProxyLayout.json.</summary>
    public static class HandPartsParser
    {
        private static Dictionary<string, PoseDto> _leftFallback;
        private static Dictionary<string, PoseDto> _rightFallback;

        public static Dictionary<string, PoseDto> ParseLeft(string json)
        {
            var live = ParseSide(json, "left_hand_display", G1LinkRegistry.LeftHandMeshParts);
            return live.Count > 0 ? live : GetFallback(true);
        }

        public static Dictionary<string, PoseDto> ParseRight(string json)
        {
            var live = ParseSide(json, "right_hand_display", G1LinkRegistry.RightHandMeshParts);
            return live.Count > 0 ? live : GetFallback(false);
        }

        public static Dictionary<string, PoseDto> GetFallback(bool left)
        {
            EnsureFallbackLoaded();
            return left ? _leftFallback : _rightFallback;
        }

        private static void EnsureFallbackLoaded()
        {
            if (_leftFallback != null)
                return;

            _leftFallback = new Dictionary<string, PoseDto>();
            _rightFallback = new Dictionary<string, PoseDto>();

            var asset = Resources.Load<TextAsset>("HandProxyLayout");
            if (asset == null)
                return;

            var layout = JsonUtility.FromJson<HandProxyLayoutDto>(asset.text);
            if (layout?.leftParts != null)
                FillParts(_leftFallback, layout.leftParts);
            if (layout?.rightParts != null)
                FillParts(_rightFallback, layout.rightParts);
        }

        private static void FillParts(Dictionary<string, PoseDto> dst, HandProxyPartDto[] parts)
        {
            foreach (var part in parts)
            {
                if (part == null || string.IsNullOrEmpty(part.name))
                    continue;
                dst[part.name] = new PoseDto { p = part.p, q = part.q };
            }
        }

        private static Dictionary<string, PoseDto> ParseSide(
            string json,
            string blockKey,
            string[] partNames)
        {
            var result = new Dictionary<string, PoseDto>();
            if (string.IsNullOrEmpty(json))
                return result;

            var key = $"\"{blockKey}\"";
            var idx = json.IndexOf(key, StringComparison.Ordinal);
            if (idx < 0)
                return result;

            foreach (var link in partNames)
            {
                var pose = VisualLinksParser.TryExtractLinkPose(json, idx, link);
                if (pose != null)
                    result[link] = pose;
            }
            return result;
        }
    }

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
}
