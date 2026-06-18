"""JSONL trajectory recorder for demo replay."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TrajectoryRecorder:
    def __init__(self, out_dir: str | Path = "recordings"):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._session_id = time.strftime("%Y%m%d_%H%M%S")
        self._path = self.out_dir / f"session_{self._session_id}.jsonl"
        self._t0 = time.time()
        self._fp = self._path.open("a", encoding="utf-8")
        print(f"[Recorder] Writing {self._path}")

    @property
    def path(self) -> Path:
        return self._path

    def write(self, sample: dict[str, Any]) -> None:
        row = {"ts": time.time() - self._t0, **sample}
        self._fp.write(json.dumps(row, default=_json_default) + "\n")
        self._fp.flush()

    def close(self) -> None:
        self._fp.close()


def _json_default(obj):
    import numpy as np

    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Not serializable: {type(obj)}")
