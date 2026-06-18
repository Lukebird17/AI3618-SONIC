"""Replay recorded JSONL over UDP for demo without wearing headset."""

from __future__ import annotations

import argparse
import json
import socket
import time
from pathlib import Path

import numpy as np

from sonic_bridge.protocol import Pose7, encode_packet


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True, help="JSONL from TrajectoryRecorder")
    p.add_argument("--udp-host", default="255.255.255.255")
    p.add_argument("--udp-port", type=int, default=17771)
    p.add_argument("--speed", type=float, default=1.0)
    args = p.parse_args()

    rows = []
    with Path(args.file).open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    if not rows:
        print("Empty recording.")
        return

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    target = (args.udp_host, args.udp_port)

    t0 = time.time()
    start_ts = rows[0]["ts"]
    print(f"[Replay] {len(rows)} frames → {target}")

    for row in rows:
        wait = (row["ts"] - start_ts) / args.speed - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)
        v = row.get("vr_3pt_pose")
        if v is None:
            continue
        arr = np.array(v)
        pkt = {
            "type": "state",
            "ts": time.time(),
            "calibrated": True,
            "alignment_score": row.get("alignment_score", 1.0),
            "safe_to_switch": True,
            "vr_3pt": {
                "left": Pose7.from_vr_row(arr[0]).to_dict(),
                "right": Pose7.from_vr_row(arr[1]).to_dict(),
                "head": Pose7.from_vr_row(arr[2]).to_dict(),
            },
        }
        sock.sendto(encode_packet(pkt), target)

    print("[Replay] Done.")


if __name__ == "__main__":
    main()
