#!/usr/bin/env python3
"""Export G1 STL meshes from SONIC deploy → Unity-importable OBJ."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# Link names must exist in G1 URDF / Pinocchio model
MESH_LINKS = [
    "pelvis",
    "pelvis_contour_link",
    "torso_link",
    "head_link",
    "waist_yaw_link",
    "waist_roll_link",
    "logo_link",
    "left_hip_pitch_link",
    "left_hip_roll_link",
    "left_hip_yaw_link",
    "left_knee_link",
    "left_ankle_pitch_link",
    "left_ankle_roll_link",
    "right_hip_pitch_link",
    "right_hip_roll_link",
    "right_hip_yaw_link",
    "right_knee_link",
    "right_ankle_pitch_link",
    "right_ankle_roll_link",
    "left_shoulder_pitch_link",
    "left_shoulder_roll_link",
    "left_shoulder_yaw_link",
    "left_elbow_link",
    "left_wrist_roll_link",
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
    "right_shoulder_pitch_link",
    "right_shoulder_roll_link",
    "right_shoulder_yaw_link",
    "right_elbow_link",
    "right_wrist_roll_link",
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
]

SKIP_STEMS = {
    "left_rubber_hand",
    "right_rubber_hand",
    "left_wrist_roll_rubber_hand",
    "right_wrist_roll_rubber_hand",
    "torso_constraint_L_link",
    "torso_constraint_R_link",
    "torso_constraint_L_rod_link",
    "torso_constraint_R_rod_link",
    "waist_constraint_L",
    "waist_constraint_R",
    "waist_support_link",
}


def stl_binary_to_obj(stl_path: Path, obj_path: Path) -> int:
    """Convert binary STL to OBJ. Returns triangle count."""
    data = stl_path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"STL too small: {stl_path}")
    tri_count = struct.unpack_from("<I", data, 80)[0]
    offset = 84
    vertices: list[tuple[float, float, float]] = []
    vindex: dict[tuple[float, float, float], int] = {}
    faces: list[tuple[int, int, int]] = []

    def vid(x: float, y: float, z: float) -> int:
        # MuJoCo (x,y,z) → Unity mesh coords (-y, z, x) at export time.
        ux, uy, uz = -y, z, x
        key = (round(ux, 5), round(uy, 5), round(uz, 5))
        if key not in vindex:
            vindex[key] = len(vertices) + 1
            vertices.append(key)
        return vindex[key]

    for _ in range(tri_count):
        if offset + 50 > len(data):
            break
        vals = struct.unpack_from("<12fH", data, offset)
        offset += 50
        _, _, _, x1, y1, z1, x2, y2, z2, x3, y3, z3, _ = vals
        faces.append((vid(x1, y1, z1), vid(x2, y2, z2), vid(x3, y3, z3)))

    lines = [f"# from {stl_path.name}", f"o {stl_path.stem}", f"g {stl_path.stem}"]
    for x, y, z in vertices:
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for a, b, c in faces:
        lines.append(f"f {a} {b} {c}")
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(faces)


def export_meshes(src_dir: Path, dst_dir: Path) -> tuple[int, int]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    missing = 0
    for link in MESH_LINKS:
        stl = src_dir / f"{link}.STL"
        if not stl.exists():
            stl = src_dir / f"{link}.stl"
        if not stl.exists():
            missing += 1
            print(f"[skip] missing {link}")
            continue
        obj = dst_dir / f"{link}.obj"
        n = stl_binary_to_obj(stl, obj)
        print(f"[ok] {link}.obj ({n} tris)")
        ok += 1
    # Also export any extra STLs not in list (except skip)
    for stl in sorted(src_dir.glob("*.STL")):
        stem = stl.stem
        if stem in SKIP_STEMS or stem in MESH_LINKS:
            continue
        obj = dst_dir / f"{stem}.obj"
        if obj.exists():
            continue
        n = stl_binary_to_obj(stl, obj)
        print(f"[extra] {stem}.obj ({n} tris)")
        ok += 1
    return ok, missing


def main() -> None:
    default = (
        Path.home()
        / "projects/GR00T-WholeBodyControl/gear_sonic/data/robot_model/model_data/g1/meshes"
    )
    sonic = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    targets = [
        Path.home() / "vr/quest-mirror-unity/Assets/Robot/G1/Meshes",
        Path.home() / "vr/quest-mirror-unity/quest mirror unity/Assets/Robot/G1/Meshes",
    ]
    if not sonic.is_dir():
        print(f"Source not found: {sonic}")
        sys.exit(1)
    for dst in targets:
        print(f"\n=== Export → {dst} ===")
        ok, missing = export_meshes(sonic, dst)
        print(f"Done: {ok} meshes, {missing} missing from list")


if __name__ == "__main__":
    main()
