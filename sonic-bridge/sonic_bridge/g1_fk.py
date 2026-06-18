"""G1 FK helpers — same frames as MuJoCo / gear_sonic get_g1_key_frame_poses."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np

from sonic_bridge.protocol import Pose7

if TYPE_CHECKING:
    pass

HEAD_LINK_LENGTH = 0.35
# Fixed T3 head — must match quest_reader VR_3PT_HEAD_*
FIXED_VR3PT_HEAD = Pose7(
    p=[0.0241, -0.0081, 0.4028],
    q=[0.9991, 0.011, 0.0402, -0.0002],
)
# g1_29dof_with_hand.urdf — d435_joint on torso_link
D435_LOCAL_POS = np.array([0.0576235, 0.01753, 0.41987], dtype=np.float64)
D435_LOCAL_RPY = np.array([0.0, 0.8307767239493009, 0.0], dtype=np.float64)
_robot_model = None


def _load_model():
    global _robot_model
    if _robot_model is not None:
        return _robot_model
    from gear_sonic.data.robot_model.instantiation.g1 import instantiate_g1_robot_model

    _robot_model = instantiate_g1_robot_model()
    return _robot_model


def _normalize_body_q(q: np.ndarray | None) -> np.ndarray:
    """Accept 29-DOF MuJoCo body_q_measured or full Pinocchio q (43)."""
    model = _load_model()
    if q is None:
        return model.get_default_body_pose()
    q = np.asarray(q, dtype=np.float64).ravel()
    if q.size == model.num_dofs:
        return q
    if q.size == 29:
        return model.get_configuration_from_actuated_joints(body_actuated_joint_values=q)
    raise ValueError(f"Expected q length 29 or {model.num_dofs}, got {q.size}")


def default_body_q() -> np.ndarray:
    model = _load_model()
    return np.asarray(model.default_body_pose, dtype=np.float64)


def _pose7_from_key(entry: dict) -> Pose7:
    p = entry["position"]
    q = entry["orientation_wxyz"]
    return Pose7(
        p=[float(p[0]), float(p[1]), float(p[2])],
        q=[float(q[0]), float(q[1]), float(q[2]), float(q[3])],
    )


def _head_from_torso(torso: dict) -> Pose7:
    """Approximate head frame from torso FK (matches vr3pt visualizer head link)."""
    from scipy.spatial.transform import Rotation as sRot

    pos = np.asarray(torso["position"], dtype=np.float64)
    q_wxyz = np.asarray(torso["orientation_wxyz"], dtype=np.float64)
    q_xyzw = [q_wxyz[1], q_wxyz[2], q_wxyz[3], q_wxyz[0]]
    rot = sRot.from_quat(q_xyzw).as_matrix()
    head_pos = pos + rot @ np.array([0.0, 0.0, HEAD_LINK_LENGTH])
    return Pose7(
        p=[float(head_pos[0]), float(head_pos[1]), float(head_pos[2])],
        q=[float(q_wxyz[0]), float(q_wxyz[1]), float(q_wxyz[2]), float(q_wxyz[3])],
    )


def d435_pose(q: np.ndarray | None = None) -> Pose7:
    """Intel RealSense D435 frame on torso (matches URDF d435_joint)."""
    from scipy.spatial.transform import Rotation as sRot

    frames = keyframe_poses(q)
    torso = frames["torso"]
    t_p = np.array(torso.p, dtype=np.float64)
    t_q = np.array(torso.q, dtype=np.float64)
    t_xyzw = [t_q[1], t_q[2], t_q[3], t_q[0]]
    rot_t = sRot.from_quat(t_xyzw).as_matrix()
    rot_local = sRot.from_euler("xyz", D435_LOCAL_RPY).as_matrix()
    rot = rot_t @ rot_local
    pos = t_p + rot_t @ D435_LOCAL_POS
    q_xyzw = sRot.from_matrix(rot).as_quat()
    return Pose7(
        p=[float(pos[0]), float(pos[1]), float(pos[2])],
        q=[float(q_xyzw[3]), float(q_xyzw[0]), float(q_xyzw[1]), float(q_xyzw[2])],
    )


def keyframe_poses(q: np.ndarray | None = None) -> dict[str, Pose7]:
    """FK poses for left/right wrist, torso, head (camera), from MuJoCo joint vector."""
    from gear_sonic.utils.teleop.vis.vr3pt_pose_visualizer import get_g1_key_frame_poses

    model = _load_model()
    if q is None:
        q = default_body_q()
    else:
        q = _normalize_body_q(q)
    raw = get_g1_key_frame_poses(model, q=np.asarray(q, dtype=np.float64))
    torso = _pose7_from_key(raw["torso"])
    return {
        "left": _pose7_from_key(raw["left_wrist"]),
        "right": _pose7_from_key(raw["right_wrist"]),
        "torso": torso,
        "head": _head_from_torso(raw["torso"]),
    }


from sonic_bridge.g1_visual_links import VISUAL_LINK_NAMES


def _pose7_from_se3(se3) -> Pose7:
    from scipy.spatial.transform import Rotation as sRot

    p = se3.translation
    rot = se3.rotation
    q_xyzw = sRot.from_matrix(rot).as_quat()
    return Pose7(
        p=[float(p[0]), float(p[1]), float(p[2])],
        q=[float(q_xyzw[3]), float(q_xyzw[0]), float(q_xyzw[1]), float(q_xyzw[2])],
    )


def visual_link_poses(
    q: np.ndarray | None = None,
    left_hand: list[float] | None = None,
    right_hand: list[float] | None = None,
) -> dict[str, Pose7]:
    """FK placement for G1 mesh segments (Unity avatar)."""
    model = _load_model()
    q_arr = np.asarray(q, dtype=np.float64).ravel() if q is not None else None
    if left_hand or right_hand:
        if q_arr is not None and q_arr.size == 29:
            body = q_arr
        elif q_arr is not None and q_arr.size == model.num_dofs:
            body = q_arr[model.get_body_actuated_joint_indices()]
        else:
            body = model.get_default_body_pose()[model.get_body_actuated_joint_indices()]
        lh = np.asarray(left_hand, dtype=np.float64) if left_hand else None
        rh = np.asarray(right_hand, dtype=np.float64) if right_hand else None
        q = model.get_configuration_from_actuated_joints(
            body_actuated_joint_values=body,
            left_hand_actuated_joint_values=lh,
            right_hand_actuated_joint_values=rh,
        )
    elif q is None:
        q = default_body_q()
    else:
        q = _normalize_body_q(q)
    q = np.asarray(q, dtype=np.float64)
    model.cache_forward_kinematics(q)
    out: dict[str, Pose7] = {}
    for name in VISUAL_LINK_NAMES:
        try:
            se3 = model.frame_placement(name)
            out[name] = _pose7_from_se3(se3)
        except Exception:
            continue
    return out


def standing_body_q() -> np.ndarray:
    """MuJoCo standing reference (DEFAULT_DOF_ANGLES in sonic WBC yaml)."""
    return default_body_q()


def synthetic_body_q(t: float) -> np.ndarray:
    """Standing pose + gentle arm motion for Editor tests without deploy."""
    q = standing_body_q().copy()
    if q.size > 14:
        q[14] += 0.15 * math.sin(t * 0.8)
    if q.size > 21:
        q[21] += 0.12 * math.sin(t * 1.1 + 0.5)
    return q
