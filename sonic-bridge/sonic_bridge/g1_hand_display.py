"""Hand mesh poses relative to wrist anchor — for Unity dexterous hand display (not cubes)."""

from __future__ import annotations

import numpy as np
from scipy.spatial.transform import Rotation as sRot

from sonic_bridge.alignment import pose7_to_4x4
from sonic_bridge.protocol import Pose7

LEFT_HAND_DISPLAY_PARTS = (
    "left_wrist_pitch_link",
    "left_wrist_yaw_link",
    "left_hand_palm_link",
    "left_hand_thumb_0_link",
    "left_hand_thumb_1_link",
    "left_hand_thumb_2_link",
    "left_hand_index_0_link",
    "left_hand_index_1_link",
    "left_hand_middle_0_link",
    "left_hand_middle_1_link",
)

RIGHT_HAND_DISPLAY_PARTS = (
    "right_wrist_pitch_link",
    "right_wrist_yaw_link",
    "right_hand_palm_link",
    "right_hand_thumb_0_link",
    "right_hand_thumb_1_link",
    "right_hand_thumb_2_link",
    "right_hand_index_0_link",
    "right_hand_index_1_link",
    "right_hand_middle_0_link",
    "right_hand_middle_1_link",
)


def _pose7_from_4x4(T: np.ndarray) -> Pose7:
    p = T[:3, 3]
    q_xyzw = sRot.from_matrix(T[:3, :3]).as_quat()
    return Pose7(
        p=[float(p[0]), float(p[1]), float(p[2])],
        q=[float(q_xyzw[3]), float(q_xyzw[0]), float(q_xyzw[1]), float(q_xyzw[2])],
    )


def hand_display_parts(visual_links: dict[str, Pose7], side: str) -> dict[str, Pose7]:
    """FK hand link poses relative to wrist_yaw anchor (matches vr_3pt wrist frame)."""
    parts = LEFT_HAND_DISPLAY_PARTS if side == "left" else RIGHT_HAND_DISPLAY_PARTS
    anchor_name = f"{side}_wrist_yaw_link"
    if anchor_name not in visual_links:
        return {}

    anchor_T = pose7_to_4x4(visual_links[anchor_name])
    anchor_inv = np.linalg.inv(anchor_T)
    out: dict[str, Pose7] = {}
    for name in parts:
        if name not in visual_links:
            continue
        rel = anchor_inv @ pose7_to_4x4(visual_links[name])
        out[name] = _pose7_from_4x4(rel)
    return out
