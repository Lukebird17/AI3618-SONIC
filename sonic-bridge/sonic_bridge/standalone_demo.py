"""Standalone UDP broadcaster with synthetic MuJoCo joint sync (Editor / no deploy)."""

from __future__ import annotations

import argparse
import math
import socket
import time

from sonic_bridge.alignment import alignment_score_pose7
from sonic_bridge.g1_fk import (
    d435_pose,
    keyframe_poses,
    synthetic_body_q,
    visual_link_poses,
)
from sonic_bridge.protocol import BridgeState, Pose7, encode_packet
from sonic_bridge.scene_layout import SCENE_NAME, pelvis_world_packet, scene_objects_packet


def _demo_vr3pt_raw(t: float, ref: dict[str, Pose7]) -> dict[str, Pose7]:
    misalign = 0.12
    sway = 0.08 * math.sin(t * 1.2)
    left = ref["left"]
    right = ref["right"]
    return {
        "left": Pose7(p=[left.p[0] + misalign + sway, left.p[1], left.p[2]], q=left.q),
        "right": Pose7(p=[right.p[0] + misalign + sway, right.p[1], right.p[2]], q=right.q),
        "head": ref["head"],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Standalone Path B demo (synthetic MuJoCo FK)")
    p.add_argument("--udp-host", default="255.255.255.255")
    p.add_argument("--udp-port", type=int, default=17771)
    p.add_argument("--hz", type=float, default=30.0)
    p.add_argument("--display-mode", default="CALIBRATION", choices=("CALIBRATION", "TELEOP"))
    args = p.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    target = (args.udp_host, args.udp_port)

    print(f"[Standalone] → {target} @ {args.hz} Hz | use run_bridge --synthetic for full pipeline")
    t0 = time.time()
    try:
        while True:
            t = time.time() - t0
            q = synthetic_body_q(t)
            frames = keyframe_poses(q)
            d435 = d435_pose(q)
            g1_ref = {"left": frames["left"], "right": frames["right"]}
            raw = _demo_vr3pt_raw(t, {**frames, **g1_ref})
            score = alignment_score_pose7(raw["left"], raw["right"], g1_ref["left"], g1_ref["right"])
            pw = pelvis_world_packet()
            state = BridgeState(
                mode="CALIBRATION",
                display_mode=args.display_mode.upper(),
                calibrated=False,
                alignment_score=score,
                safe_to_switch=score >= 0.75,
                latency_ms=8.0 + 5 * abs(math.sin(t)),
                vr_3pt_raw=raw,
                g1_ref=g1_ref,
                robot_joints=[float(x) for x in q],
                robot_actual={
                    "left": frames["left"],
                    "right": frames["right"],
                    "head": frames["head"],
                    "torso": frames["torso"],
                },
                camera_pose=frames["head"],
                mirror_camera_pose=frames["head"],
                d435_pose=d435,
                visual_links=visual_link_poses(q),
                pelvis_world=Pose7(p=pw["p"], q=pw["q"]),
                scene_name=SCENE_NAME,
                scene_objects=scene_objects_packet(),
            )
            sock.sendto(encode_packet(state.to_packet("ghost")), target)
            time.sleep(1.0 / args.hz)
    except KeyboardInterrupt:
        print("\n[Standalone] Done.")


if __name__ == "__main__":
    main()
