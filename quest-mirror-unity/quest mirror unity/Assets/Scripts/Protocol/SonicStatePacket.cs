using System;
using UnityEngine;

namespace SonicQuestMirror.Protocol
{
    [Serializable]
    public class HandStateDto
    {
        public float left_trigger;
        public float right_trigger;
        public float left_grip;
        public float right_grip;
    }

    [Serializable]
    public class VisualLinksDto
    {
        public PoseDto pelvis;
        public PoseDto torso_link;
        public PoseDto head_link;
        public PoseDto left_shoulder_pitch_link;
        public PoseDto left_elbow_link;
        public PoseDto left_wrist_yaw_link;
        public PoseDto left_hand_palm_link;
        public PoseDto right_shoulder_pitch_link;
        public PoseDto right_elbow_link;
        public PoseDto right_wrist_yaw_link;
        public PoseDto right_hand_palm_link;
        public PoseDto left_hip_pitch_link;
        public PoseDto left_knee_link;
        public PoseDto left_ankle_roll_link;
        public PoseDto right_hip_pitch_link;
        public PoseDto right_knee_link;
        public PoseDto right_ankle_roll_link;
    }

    [Serializable]
    public class PoseDto
    {
        public float[] p;
        public float[] q;
    }

    [Serializable]
    public class Vr3PtDto
    {
        public PoseDto left;
        public PoseDto right;
        public PoseDto head;
    }

    [Serializable]
    public class RobotActualDto
    {
        public PoseDto left;
        public PoseDto right;
        public PoseDto head;
        public PoseDto torso;
    }

    [Serializable]
    public class StatePacket
    {
        public string type;
        public double ts;
        public string mode;
        public string display_mode;
        public bool recording;
        public string recording_path;
        public bool calibrated;
        public float alignment_score;
        public bool safe_to_switch;
        public float latency_ms;
        public Vr3PtDto vr_3pt;
        public Vr3PtDto vr_3pt_raw;
        public Vr3PtDto g1_ref;
        public RobotActualDto robot_actual;
        public PoseDto camera_pose;
        public PoseDto d435_pose;
        public PoseDto mirror_camera_pose;
        public PoseDto unity_head_pose;
        public float[] robot_joints;
        public HandStateDto hand_state;
        public float[] left_hand_joints;
        public float[] right_hand_joints;
        public VisualLinksDto visual_links;
        public PoseDto pelvis_world;
        public string scene_name;
    }

    public static class PoseMath
    {
        /// <summary>
        /// MuJoCo / URDF: X forward, Y left, Z up → Unity: X right, Y up, Z forward.
        /// Positions: p_u = S·p_m with S mapping (x,y,z)_m → (-y,z,x)_u.
        /// Rotations (same axis labels): R_u = S·R_m; mesh links also apply Z-up STL fix.
        /// </summary>
        private static readonly Quaternion LinkMeshBasis = Quaternion.Euler(-90f, 0f, 0f);

        public static Vector3 MuJoCoToUnityPosition(PoseDto pose)
        {
            if (pose?.p == null || pose.p.Length < 3)
                return Vector3.zero;
            return MuJoCoToUnityPosition(pose.p[0], pose.p[1], pose.p[2]);
        }

        public static Vector3 MuJoCoToUnityPosition(float x, float y, float z) =>
            new Vector3(-y, z, x);

        public static Quaternion MuJoCoToUnityRotation(PoseDto pose)
        {
            if (pose?.q == null || pose.q.Length < 4)
                return LinkMeshBasis;
            return MuJoCoToUnityRotation(pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
        }

        public static Quaternion MuJoCoToUnityRotation(float w, float x, float y, float z)
        {
            var similar = SimilarityRotation(w, x, y, z);
            return similar * LinkMeshBasis;
        }

        /// <summary>Camera / wrist-only poses (no URDF mesh Z-up fix).</summary>
        public static Quaternion MuJoCoToUnityRotationPoseOnly(float w, float x, float y, float z) =>
            SimilarityRotation(w, x, y, z);

        /// <summary>
        /// MuJoCo head FK → Unity camera. MuJoCo +X (sight) maps to Unity +Z; MuJoCo +Z → Unity +Y.
        /// </summary>
        public static Quaternion MuJoCoToUnityCameraRotation(float w, float x, float y, float z)
        {
            var head = SimilarityRotation(w, x, y, z);
            var forward = head * Vector3.forward;
            var up = head * Vector3.up;
            if (forward.sqrMagnitude < 1e-8f || up.sqrMagnitude < 1e-8f)
                return head;
            return Quaternion.LookRotation(forward, up);
        }

        public static void ApplyPose(Transform target, PoseDto pose)
        {
            if (pose?.p == null || pose.p.Length < 3) return;
            target.localPosition = MuJoCoToUnityPosition(pose);
            if (pose.q != null && pose.q.Length >= 4)
                target.localRotation = MuJoCoToUnityRotation(pose);
        }

        public static void ApplyPoseNoMeshBasis(Transform target, PoseDto pose)
        {
            if (pose?.p == null || pose.p.Length < 3) return;
            target.localPosition = MuJoCoToUnityPosition(pose);
            if (pose.q != null && pose.q.Length >= 4)
                target.localRotation = MuJoCoToUnityRotationPoseOnly(pose.q[0], pose.q[1], pose.q[2], pose.q[3]);
        }

        public static bool HasPose(PoseDto pose) =>
            pose?.p != null && pose.p.Length >= 3;

        /// <summary>R_u = S · R(wxyz), S mapping (x,y,z)_m → (-y,z,x)_u.</summary>
        private static Quaternion SimilarityRotation(float w, float x, float y, float z)
        {
            var q = new Quaternion(x, y, z, w);
            var m = Matrix4x4.Rotate(q);
            var r00 = -m.m10;
            var r01 = -m.m11;
            var r02 = -m.m12;
            var r10 = m.m20;
            var r11 = m.m21;
            var r12 = m.m22;
            var r20 = m.m00;
            var r21 = m.m01;
            var r22 = m.m02;
            var ru = new Matrix4x4(
                new Vector4(r00, r10, r20, 0f),
                new Vector4(r01, r11, r21, 0f),
                new Vector4(r02, r12, r22, 0f),
                new Vector4(0f, 0f, 0f, 1f));
            return ru.rotation;
        }
    }
}
