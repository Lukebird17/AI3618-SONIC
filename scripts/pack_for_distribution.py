#!/usr/bin/env python3
"""Pack vr project for distribution (exclude large/cache files)."""

from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path

VR_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = Path.home() / "AI3618-Quest-VR-Teleop.zip"
ARCHIVE_NAME = "AI3618-Quest-VR-Teleop"

SKIP_DIR_NAMES = {
    "Library",
    "Builds",
    "Temp",
    "Logs",
    "obj",
    "__pycache__",
    "sonic_bridge.egg-info",
    "quest-mirror-unity-old",
    "unitree_lfs",
    ".git",
}
SKIP_FILE_NAMES = {"main.zip", "reference.zip"}


def should_skip_dir(name: str) -> bool:
    return name in SKIP_DIR_NAMES


def should_skip_file(rel: Path) -> bool:
    if rel.name in SKIP_FILE_NAMES:
        return True
    if rel.name.startswith("TensorRT-") and rel.suffix == ".gz":
        return True
    if rel.match("sonic-bridge/recordings/session_*.jsonl"):
        return True
    return False


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    sample_rec = None
    rec_dir = VR_ROOT / "sonic-bridge" / "recordings"
    samples = sorted(
        (p for p in rec_dir.glob("session_*.jsonl") if p.stat().st_size < 5 * 1024 * 1024),
        key=lambda p: p.stat().st_size,
    )
    if samples:
        sample_rec = samples[-1]

    if out.exists():
        out.unlink()

    count = 0
    print(f"Packing {VR_ROOT} -> {out}")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(VR_ROOT):
            dirs[:] = [d for d in dirs if not should_skip_dir(d)]
            root_path = Path(root)
            for name in files:
                fp = root_path / name
                rel = fp.relative_to(VR_ROOT)
                if should_skip_file(rel):
                    continue
                arc = Path(ARCHIVE_NAME) / rel
                zf.write(fp, arc.as_posix())
                count += 1
                if count % 500 == 0:
                    print(f"  ... {count} files")

        if sample_rec and sample_rec.is_file():
            arc = Path(ARCHIVE_NAME) / "sonic-bridge" / "recordings" / sample_rec.name
            zf.write(sample_rec, arc.as_posix())
            print(f"Included sample recording: {sample_rec.name}")

    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"Done: {out} ({size_mb:.1f} MB, {count} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
