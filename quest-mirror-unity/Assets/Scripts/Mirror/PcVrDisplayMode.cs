using UnityEngine;

namespace SonicQuestMirror.Mirror
{
    /// <summary>
    /// Keep VR on Quest Link HMD but free the PC monitor (MuJoCo, terminals, etc.).
    /// </summary>
    public static class PcVrDisplayMode
    {
        private static bool _applied;

        public static void ReleasePcMonitor(int width = 480, int height = 270)
        {
            if (_applied)
                return;
            _applied = true;

#if UNITY_STANDALONE_WIN && !UNITY_EDITOR
            Application.runInBackground = true;
            Screen.fullScreenMode = FullScreenMode.Windowed;
            Screen.SetResolution(width, height, FullScreenMode.Windowed);
            Debug.Log(
                "[VR] PC 窗口已缩小为窗口模式（VR 仍在头显）。" +
                "可最小化该窗口，桌面留给 MuJoCo / 其他工具。");
#else
            Debug.Log("[VR] PcVrDisplayMode: editor / non-Windows — skipped.");
#endif
        }
    }
}
