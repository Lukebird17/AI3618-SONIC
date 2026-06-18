"""Subscribe to deploy MuJoCo feedback (g1_debug @ :5557)."""

from __future__ import annotations

import msgpack
import numpy as np
import zmq


class MujocoFeedbackReader:
    """Non-blocking reader for latest body_q_measured from g1_deploy_onnx_ref."""

    def __init__(self, host: str = "localhost", port: int = 5557, topic: str = "g1_debug"):
        self._topic = topic.encode("utf-8")
        self._topic_len = len(self._topic)
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)
        self._sock.setsockopt(zmq.CONFLATE, 1)
        self._sock.setsockopt(zmq.RCVTIMEO, 0)
        self._sock.setsockopt_string(zmq.SUBSCRIBE, topic)
        self._sock.connect(f"tcp://{host}:{port}")
        self._last_q: np.ndarray | None = None

    def close(self) -> None:
        self._sock.close(linger=0)

    def poll(self) -> np.ndarray | None:
        """Return latest 29-DOF body_q_measured, or cached value if no new packet."""
        try:
            raw = self._sock.recv(zmq.NOBLOCK)
        except zmq.Again:
            return self._last_q
        except zmq.ZMQError:
            return self._last_q

        payload = raw[self._topic_len :]
        try:
            unpacked = msgpack.unpackb(payload, raw=False)
        except Exception:
            return self._last_q

        q = unpacked.get("body_q_measured")
        if q is None:
            return self._last_q

        self._last_q = np.asarray(q, dtype=np.float64)
        return self._last_q
