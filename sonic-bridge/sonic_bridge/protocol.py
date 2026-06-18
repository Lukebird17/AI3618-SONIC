"""UDP JSON protocol helpers aligned with docs/PROTOCOL.md."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Pose7:
    p: list[float]
    q: list[float]  # wxyz

    @classmethod
    def from_vr_row(cls, row) -> "Pose7":
        return cls(p=[float(row[0]), float(row[1]), float(row[2])],
                   q=[float(row[3]), float(row[4]), float(row[5]), float(row[6])])

    def to_dict(self) -> dict[str, list[float]]:
        return {"p": self.p, "q": self.q}


@dataclass
class BridgeState:
    mode: str = "IDLE"
    display_mode: str = "CALIBRATION"  # CALIBRATION | TELEOP (Unity HUD)
    recording: bool = False
    recording_path: str | None = None
    calibrated: bool = False
    alignment_score: float = 0.0
    safe_to_switch: bool = False
    latency_ms: float = 0.0
    vr_3pt: dict[str, Pose7] = field(default_factory=dict)
    vr_3pt_raw: dict[str, Pose7] = field(default_factory=dict)
    g1_ref: dict[str, Pose7] = field(default_factory=dict)
    robot_joints: list[float] | None = None
    robot_actual: dict[str, Pose7] = field(default_factory=dict)
    camera_pose: Pose7 | None = None
    d435_pose: Pose7 | None = None
    mirror_camera_pose: Pose7 | None = None
    unity_head_pose: Pose7 | None = None
    hmd_view_pose: Pose7 | None = None
    hand_state: dict[str, float] = field(default_factory=dict)
    left_hand_joints: list[float] | None = None
    right_hand_joints: list[float] | None = None
    visual_links: dict[str, Pose7] = field(default_factory=dict)
    left_hand_display: dict[str, Pose7] = field(default_factory=dict)
    right_hand_display: dict[str, Pose7] = field(default_factory=dict)
    pelvis_world: Pose7 | None = None
    scene_name: str | None = None
    scene_objects: list[dict] | None = None

    def to_packet(self, pkt_type: str = "state") -> dict[str, Any]:
        body: dict[str, Any] = {
            "type": pkt_type,
            "ts": time.time(),
            "mode": self.mode,
            "display_mode": self.display_mode,
            "recording": self.recording,
            "calibrated": self.calibrated,
            "alignment_score": round(self.alignment_score, 4),
            "safe_to_switch": self.safe_to_switch,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.recording_path:
            body["recording_path"] = self.recording_path
        if self.vr_3pt:
            body["vr_3pt"] = {k: v.to_dict() for k, v in self.vr_3pt.items()}
        if self.vr_3pt_raw:
            body["vr_3pt_raw"] = {k: v.to_dict() for k, v in self.vr_3pt_raw.items()}
        if self.g1_ref:
            body["g1_ref"] = {k: v.to_dict() for k, v in self.g1_ref.items()}
        if self.robot_actual:
            body["robot_actual"] = {k: v.to_dict() for k, v in self.robot_actual.items()}
        if self.camera_pose is not None:
            body["camera_pose"] = self.camera_pose.to_dict()
        if self.d435_pose is not None:
            body["d435_pose"] = self.d435_pose.to_dict()
        if self.mirror_camera_pose is not None:
            body["mirror_camera_pose"] = self.mirror_camera_pose.to_dict()
        if self.unity_head_pose is not None:
            body["unity_head_pose"] = self.unity_head_pose.to_dict()
        if self.hmd_view_pose is not None:
            body["hmd_view_pose"] = self.hmd_view_pose.to_dict()
        if self.robot_joints is not None:
            body["robot_joints"] = self.robot_joints
        if self.hand_state:
            body["hand_state"] = self.hand_state
        if self.left_hand_joints is not None:
            body["left_hand_joints"] = self.left_hand_joints
        if self.right_hand_joints is not None:
            body["right_hand_joints"] = self.right_hand_joints
        if self.visual_links:
            body["visual_links"] = {k: v.to_dict() for k, v in self.visual_links.items()}
        if self.left_hand_display:
            body["left_hand_display"] = {k: v.to_dict() for k, v in self.left_hand_display.items()}
        if self.right_hand_display:
            body["right_hand_display"] = {k: v.to_dict() for k, v in self.right_hand_display.items()}
        if self.pelvis_world is not None:
            body["pelvis_world"] = self.pelvis_world.to_dict()
        if self.scene_name:
            body["scene_name"] = self.scene_name
        if self.scene_objects:
            body["scene_objects"] = self.scene_objects
        return body


def encode_packet(packet: dict[str, Any]) -> bytes:
    return json.dumps(packet, separators=(",", ":")).encode("utf-8")


def decode_packet(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"))
