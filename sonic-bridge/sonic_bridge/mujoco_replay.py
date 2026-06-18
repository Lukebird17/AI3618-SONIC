"""Replay bridge JSONL or official manager NPZ into MuJoCo via ZMQ (and optional Unity UDP)."""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

import numpy as np

from sonic_bridge.hand_ik import compute_hand_joints
from sonic_bridge.protocol import Pose7, encode_packet


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _vr_arrays_from_row(row: dict) -> tuple[np.ndarray, np.ndarray] | None:
    v = row.get("vr_3pt_pose")
    if v is None:
        return None
    arr = np.asarray(v, dtype=np.float64)
    if arr.shape != (3, 7):
        return None
    pos = arr[:, :3].reshape(-1).astype(np.float32)
    quat = arr[:, 3:7].reshape(-1).astype(np.float32)  # wxyz per point
    return pos, quat


def _neutral_smpl_buffers() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Standing neutral SMPL buffers (manager-compatible shapes)."""
    smpl_pose = np.zeros((1, 21, 3), dtype=np.float32)
    smpl_joints = np.zeros((1, 22, 3), dtype=np.float32)
    body_quat = np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32)
    return smpl_pose, smpl_joints, body_quat


def _pack_pose_zmq(
    vr_pos: np.ndarray,
    vr_quat: np.ndarray,
    left_hand: list[float],
    right_hand: list[float],
    frame_index: int,
) -> bytes:
    from gear_sonic.utils.teleop.zmq.zmq_planner_sender import pack_pose_message

    smpl_pose, smpl_joints, body_quat = _neutral_smpl_buffers()
    data = {
        "smpl_pose": smpl_pose.reshape(1, 21, 3),
        "smpl_joints": smpl_joints.reshape(1, 22, 3),
        "body_quat_w": body_quat,
        "joint_pos": np.zeros((1, 29), dtype=np.float32),
        "joint_vel": np.zeros((1, 29), dtype=np.float32),
        "vr_position": vr_pos.reshape(9),
        "vr_orientation": vr_quat.reshape(12),
        "frame_index": np.array([frame_index], dtype=np.int64),
        "left_hand_joints": np.asarray(left_hand, dtype=np.float32).reshape(7),
        "right_hand_joints": np.asarray(right_hand, dtype=np.float32).reshape(7),
    }
    return pack_pose_message(data, topic="pose", version=3)


def replay_jsonl_zmq(
    path: Path,
    host: str,
    port: int,
    speed: float,
    loop: bool,
) -> None:
    import zmq

    rows = _load_jsonl(path)
    usable = [r for r in rows if _vr_arrays_from_row(r) is not None]
    if not usable:
        print(f"[MuJoCo Replay] No vr_3pt_pose rows in {path}")
        return

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PUB)
    sock.bind(f"tcp://*:{port}")
    time.sleep(0.3)
    print(f"[MuJoCo Replay] JSONL → ZMQ tcp://*:{port}  ({len(usable)} frames, speed={speed})")
    print("[MuJoCo Replay] Requires T1 sim + T2 deploy --input-type zmq_manager in VR_3PT.")

    frame_idx = 0
    while True:
        t0 = time.time()
        start_ts = usable[0]["ts"]
        for row in usable:
            wait = (row["ts"] - start_ts) / speed - (time.time() - t0)
            if wait > 0:
                time.sleep(wait)

            vr_pos, vr_quat = _vr_arrays_from_row(row)  # type: ignore[misc]
            hand = row.get("hand_state") or {}
            lh, rh = compute_hand_joints(hand)
            if row.get("left_hand_joints"):
                lh = row["left_hand_joints"]
            if row.get("right_hand_joints"):
                rh = row["right_hand_joints"]

            msg = _pack_pose_zmq(vr_pos, vr_quat, lh, rh, frame_idx)
            sock.send(msg)
            frame_idx += 1

        if not loop:
            break
        print("[MuJoCo Replay] Loop restart.")

    sock.close()
    ctx.term()
    print("[MuJoCo Replay] Done.")


def replay_npz_zmq(npz_dir: Path, host: str, port: int, speed: float, loop: bool) -> None:
    """Replay official manager pose_*.npz (full SONIC fidelity)."""
    import zmq
    from gear_sonic.utils.teleop.zmq.zmq_planner_sender import pack_pose_message

    files = sorted(npz_dir.glob("pose_*.npz"))
    if not files:
        print(f"[MuJoCo Replay] No pose_*.npz in {npz_dir}")
        return

    ctx = zmq.Context()
    sock = ctx.socket(zmq.PUB)
    sock.bind(f"tcp://*:{port}")
    time.sleep(0.3)
    print(f"[MuJoCo Replay] NPZ → ZMQ tcp://*:{port}  ({len(files)} files)")

    while True:
        t0 = time.time()
        for i, fpath in enumerate(files):
            data = np.load(fpath)
            msg = pack_pose_message(dict(data), topic="pose", version=3)
            sock.send(msg)
            if i > 0:
                dt = 1.0 / 50.0 / speed
                elapsed = time.time() - t0
                if elapsed < i * dt:
                    time.sleep(i * dt - elapsed)
        if not loop:
            break

    sock.close()
    ctx.term()
    print("[MuJoCo Replay] Done.")


def replay_jsonl_udp(path: Path, udp_host: str, udp_port: int, speed: float) -> None:
    rows = _load_jsonl(path)
    if not rows:
        print("Empty recording.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    target = (udp_host, udp_port)

    t0 = time.time()
    start_ts = rows[0]["ts"]
    print(f"[UDP Replay] {len(rows)} rows → {target}")

    for row in rows:
        wait = (row["ts"] - start_ts) / speed - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)
        v = row.get("vr_3pt_pose")
        if v is None:
            continue
        arr = np.array(v)
        pkt = {
            "type": "state",
            "ts": time.time(),
            "display_mode": row.get("display_mode", "TELEOP"),
            "recording": False,
            "calibrated": True,
            "alignment_score": row.get("alignment_score", 1.0),
            "safe_to_switch": True,
            "vr_3pt": {
                "left": Pose7.from_vr_row(arr[0]).to_dict(),
                "right": Pose7.from_vr_row(arr[1]).to_dict(),
                "head": Pose7.from_vr_row(arr[2]).to_dict(),
            },
        }
        if row.get("robot_joints"):
            pkt["robot_joints"] = row["robot_joints"]
        sock.sendto(encode_packet(pkt), target)

    print("[UDP Replay] Done.")


def main() -> None:
    p = argparse.ArgumentParser(description="Replay recordings to MuJoCo (ZMQ) or Unity (UDP)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--jsonl", type=Path, help="Bridge JSONL session file")
    src.add_argument("--npz-dir", type=Path, help="Official manager pose_*.npz directory")
    p.add_argument("--target", choices=("zmq", "udp", "both"), default="zmq")
    p.add_argument("--zmq-port", type=int, default=5556)
    p.add_argument("--udp-host", default="255.255.255.255")
    p.add_argument("--udp-port", type=int, default=17771)
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--loop", action="store_true")
    args = p.parse_args()

    if args.jsonl:
        if args.target in ("zmq", "both"):
            replay_jsonl_zmq(args.jsonl, "localhost", args.zmq_port, args.speed, args.loop)
        if args.target in ("udp", "both"):
            replay_jsonl_udp(args.jsonl, args.udp_host, args.udp_port, args.speed)
    elif args.npz_dir:
        if args.target != "zmq":
            print("[MuJoCo Replay] NPZ source only supports --target zmq")
            return
        replay_npz_zmq(args.npz_dir, "localhost", args.zmq_port, args.speed, args.loop)


if __name__ == "__main__":
    main()
