"""Export G1 hand mesh layout (palm + fingers) relative to wrist_yaw for Unity proxies."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as sRot

from sonic_bridge.alignment import pose7_to_4x4
from sonic_bridge.g1_fk import standing_body_q, visual_link_poses

LEFT_PARTS = (
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

RIGHT_PARTS = (
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


def _rel_part(anchor_T: np.ndarray, link_T: np.ndarray) -> dict:
    rel = np.linalg.inv(anchor_T) @ link_T
    p = rel[:3, 3]
    q_xyzw = sRot.from_matrix(rel[:3, :3]).as_quat()
    q_wxyz = [float(q_xyzw[3]), float(q_xyzw[0]), float(q_xyzw[1]), float(q_xyzw[2])]
    return {
        "p": [float(p[0]), float(p[1]), float(p[2])],
        "q": q_wxyz,
    }


def build_hand_proxy_layout() -> dict:
    q = standing_body_q()
    links = visual_link_poses(q)

    def side(parts: tuple[str, ...], anchor_name: str) -> list[dict]:
        anchor_T = pose7_to_4x4(links[anchor_name])
        out_parts: list[dict] = []
        for name in parts:
            if name not in links:
                continue
            out_parts.append({"name": name, **_rel_part(anchor_T, pose7_to_4x4(links[name]))})
        return out_parts

    return {
        "leftAnchor": "left_wrist_yaw_link",
        "leftParts": side(LEFT_PARTS, "left_wrist_yaw_link"),
        "rightAnchor": "right_wrist_yaw_link",
        "rightParts": side(RIGHT_PARTS, "right_wrist_yaw_link"),
    }


def export_json(out_path: Path) -> None:
    data = build_hand_proxy_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[HandProxy] Wrote {out_path} ({len(data['leftParts'])} + {len(data['rightParts'])} parts)")


def main() -> None:
    targets = [
        Path.home() / "vr/quest-mirror-unity/Assets/Resources/HandProxyLayout.json",
        Path.home()
        / "vr/quest-mirror-unity/quest mirror unity/Assets/Resources/HandProxyLayout.json",
    ]
    for t in targets:
        export_json(t)


if __name__ == "__main__":
    main()
