"""Shared MuJoCo ↔ Unity scene layout (single source of truth)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PELVIS_WORLD_POS = [0.0, 0.0, 0.793]
PELVIS_WORLD_QUAT_WXYZ = [1.0, 0.0, 0.0, 0.0]
SCENE_NAME = "unity_minimal"


@dataclass(frozen=True)
class SceneObject:
    name: str
    kind: str
    pos: list[float]
    size: list[float]
    rgba: list[float]
    fromto: list[float] | None = None


# Unity builds floor+table in editor (MujocoSceneBuilder). Bridge only needs pelvis height.
SCENE_OBJECTS: tuple[SceneObject, ...] = (
    SceneObject("floor", "plane", [0.0, 0.0, 0.0], [0.0, 0.0, 0.05], [0.28, 0.3, 0.34, 1.0]),
)


def scene_objects_packet() -> list[dict]:
    out = []
    for obj in SCENE_OBJECTS:
        row = {
            "name": obj.name,
            "kind": obj.kind,
            "pos": obj.pos,
            "size": obj.size,
            "rgba": obj.rgba,
        }
        if obj.fromto:
            row["fromto"] = obj.fromto
        out.append(row)
    return out


def pelvis_world_packet() -> dict:
    return {"p": PELVIS_WORLD_POS, "q": PELVIS_WORLD_QUAT_WXYZ}


def export_json(out_path: Path) -> None:
    data = {
        "scene": SCENE_NAME,
        "pelvis_world": pelvis_world_packet(),
        "objects": scene_objects_packet(),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[SceneLayout] Wrote {out_path}")


def main() -> None:
    from sonic_bridge.hand_proxy_layout import export_json as export_hand

    targets = [
        Path.home() / "vr/quest-mirror-unity/Assets/Resources/MujocoSceneLayout.json",
        Path.home() / "vr/quest-mirror-unity/quest mirror unity/Assets/Resources/MujocoSceneLayout.json",
    ]
    for t in targets:
        export_json(t)

    hand_targets = [
        Path.home() / "vr/quest-mirror-unity/Assets/Resources/HandProxyLayout.json",
        Path.home()
        / "vr/quest-mirror-unity/quest mirror unity/Assets/Resources/HandProxyLayout.json",
    ]
    for t in hand_targets:
        export_hand(t)


if __name__ == "__main__":
    main()
