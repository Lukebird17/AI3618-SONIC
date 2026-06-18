"""Pose alignment score vs G1 reference wrists (innovation: safe mode switch)."""

from __future__ import annotations

import math

import numpy as np


def _quat_wxyz_to_rot(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


def _pose_error(left: np.ndarray, right: np.ndarray, ref_left: np.ndarray, ref_right: np.ndarray) -> tuple[float, float]:
    """Return (position_err_m, angle_err_rad) averaged over both wrists."""
    pos_err = 0.0
    ang_err = 0.0
    for cur, ref in ((left, ref_left), (right, ref_right)):
        pos_err += float(np.linalg.norm(cur[:3, 3] - ref[:3, 3]))
        r_cur = cur[:3, :3]
        r_ref = ref[:3, :3]
        r_delta = r_ref.T @ r_cur
        trace = np.clip((np.trace(r_delta) - 1.0) / 2.0, -1.0, 1.0)
        ang_err += math.acos(trace)
    return pos_err / 2.0, ang_err / 2.0


def alignment_score(
    left_pose: np.ndarray,
    right_pose: np.ndarray,
    ref_left: np.ndarray,
    ref_right: np.ndarray,
    pos_tol_m: float = 0.08,
    ang_tol_rad: float = 0.45,
) -> float:
    """
    Map pose error to 0..1 score (1 = well aligned with G1 default).
    Thresholds tuned for course demo; adjust after first lab session.
    """
    pos_e, ang_e = _pose_error(left_pose, right_pose, ref_left, ref_right)
    pos_s = max(0.0, 1.0 - pos_e / pos_tol_m)
    ang_s = max(0.0, 1.0 - ang_e / ang_tol_rad)
    return float(np.clip(0.5 * pos_s + 0.5 * ang_s, 0.0, 1.0))


def pose7_to_4x4(p) -> np.ndarray:
    """Build 4x4 from Pose7 (wxyz)."""
    from scipy.spatial.transform import Rotation as sRot

    t = np.eye(4)
    t[:3, 3] = p.p
    q_wxyz = p.q
    q_xyzw = [q_wxyz[1], q_wxyz[2], q_wxyz[3], q_wxyz[0]]
    t[:3, :3] = sRot.from_quat(q_xyzw).as_matrix()
    return t


def alignment_score_pose7(left, right, ref_left, ref_right, **kwargs) -> float:
    """Align score vs dynamic g1_ref (MuJoCo-synced ghost wrists)."""
    return alignment_score(
        pose7_to_4x4(left),
        pose7_to_4x4(right),
        pose7_to_4x4(ref_left),
        pose7_to_4x4(ref_right),
        **kwargs,
    )


def vr3pt_rows_to_poses(vr_3pt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build 4x4 wrist poses from vr_3pt rows 0/1 (position + wxyz quat)."""
    from scipy.spatial.transform import Rotation as sRot

    def row_to_4x4(row: np.ndarray) -> np.ndarray:
        t = np.eye(4)
        t[:3, 3] = row[:3]
        q_wxyz = row[3:7]
        q_xyzw = [q_wxyz[1], q_wxyz[2], q_wxyz[3], q_wxyz[0]]
        t[:3, :3] = sRot.from_quat(q_xyzw).as_matrix()
        return t

    return row_to_4x4(vr_3pt[0]), row_to_4x4(vr_3pt[1])
