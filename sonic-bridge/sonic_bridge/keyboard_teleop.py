"""Keyboard VR_3PT substitute for Editor / WSL testing (no Quest).

MuJoCo pelvis frame: X forward, Y left, Z up. All positions in meters.
"""

from __future__ import annotations

import select
import sys
import termios
import tty
from dataclasses import dataclass, field

from sonic_bridge.protocol import Pose7


def _copy_pose(p: Pose7) -> Pose7:
    return Pose7(p=list(p.p), q=list(p.q))


def _default_poses() -> tuple[Pose7, Pose7, Pose7]:
    left = Pose7(p=[0.15, 0.25, 0.45], q=[1.0, 0.0, 0.0, 0.0])
    right = Pose7(p=[0.15, -0.25, 0.45], q=[1.0, 0.0, 0.0, 0.0])
    head = Pose7(p=[0.024, -0.008, 0.403], q=[0.999, 0.011, 0.04, 0.0])
    return left, right, head


def _yaw_pose_z(pose: Pose7, delta_rad: float) -> Pose7:
    from scipy.spatial.transform import Rotation as sRot

    q_wxyz = pose.q
    q_xyzw = [q_wxyz[1], q_wxyz[2], q_wxyz[3], q_wxyz[0]]
    rot = sRot.from_quat(q_xyzw)
    yaw = sRot.from_euler("z", delta_rad)
    out = (yaw * rot).as_quat()
    return Pose7(p=list(pose.p), q=[float(out[3]), float(out[0]), float(out[1]), float(out[2])])


def _nudge(p: Pose7, dx: float, dy: float, dz: float) -> Pose7:
    return Pose7(
        p=[p.p[0] + dx, p.p[1] + dy, p.p[2] + dz],
        q=list(p.q),
    )


HELP_TEXT = """
╔══════════════════════════════════════════════════════════════════╗
║  Keyboard VR_3PT（替代 Quest 手柄，终端需焦点）                    ║
╠══════════════════════════════════════════════════════════════════╣
║  左手 EEF (pelvis 系)     │  右手 EEF                            ║
║  Q/A  X 前/后             │  I/K  X 前/后                        ║
║  W/S  Y 左/右             │  O/L  Y 左/右                        ║
║  E/D  Z 上/下             │  P/;  Z 上/下                        ║
╠══════════════════════════════════════════════════════════════════╣
║  F/J  头显绕 Z 左/右转（仅 Unity 视角 unity_head_pose，不影响 T3 固定头） ║
║  R    腕位重置到当前 MuJoCo 幽灵腕 (g1_ref)                       ║
╠══════════════════════════════════════════════════════════════════╣
║  C    右扳机 — SONIC 腕校准（锁定当前腕为 vr_3pt）                ║
║  Y    切换 Unity CALIBRATION ↔ TELEOP（需已校准 + Align 达标）    ║
║  X    开始/停止 JSONL 录制                                        ║
║  H    显示本帮助                                                  ║
║  Ctrl+C  退出                                                     ║
╚══════════════════════════════════════════════════════════════════╝
"""


@dataclass
class KeyboardTeleop:
    step_pos: float = 0.012
    step_yaw: float = 0.045
    left: Pose7 = field(default_factory=lambda: _default_poses()[0])
    right: Pose7 = field(default_factory=lambda: _default_poses()[1])
    head: Pose7 = field(default_factory=lambda: _default_poses()[2])
    calibrated: bool = False
    _old_term: list | None = field(default=None, repr=False)
    _active: bool = field(default=False, repr=False)
    _pending_reset: bool = field(default=False, repr=False)

    def start(self) -> bool:
        if not sys.stdin.isatty():
            print("[KeyboardTeleop] stdin 不是 TTY，无法读键。请在 WSL 终端直接运行（勿后台）。")
            return False
        self._old_term = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        self._active = True
        print(HELP_TEXT)
        return True

    def stop(self) -> None:
        if self._active and self._old_term is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_term)
        self._active = False
        self._old_term = None

    def reset_to_ref(self, ref: dict[str, Pose7] | None, head_ref: Pose7 | None = None) -> None:
        if not ref or not ref.get("left") or not ref.get("right"):
            left, right, head = _default_poses()
            self.left = left
            self.right = right
            self.head = head_ref or head
            return
        # Start slightly offset so user can test alignment by moving keys
        self.left = _nudge(_copy_pose(ref["left"]), 0.06, 0.0, 0.0)
        self.right = _nudge(_copy_pose(ref["right"]), 0.06, 0.0, 0.0)
        if head_ref:
            self.head = _copy_pose(head_ref)
        elif ref.get("head"):
            self.head = _copy_pose(ref["head"])

    def poll(self) -> dict | None:
        """Non-blocking key poll. Returns Quest-like button dict or None."""
        if not self._active:
            return None

        buttons: dict | None = None
        while select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if not ch:
                break
            key = ch.lower()
            if key == "\x03":  # Ctrl+C handled by outer try
                break
            if key == "h":
                print(HELP_TEXT)
                continue
            if key == "r":
                print("[KeyboardTeleop] R → 下次循环重置到 g1_ref（带初始偏移）")
                self._pending_reset = True
                continue
            if key == "c":
                self.calibrated = True
                print("[KeyboardTeleop] C → 右扳机校准 (quest_calibrated=True)")
                continue
            if key == "y":
                buttons = {"button_y": True, "button_x": False}
                continue
            if key == "x":
                buttons = {"button_y": False, "button_x": True}
                continue

            sp = self.step_pos
            if key == "q":
                self.left = _nudge(self.left, sp, 0, 0)
            elif key == "a":
                self.left = _nudge(self.left, -sp, 0, 0)
            elif key == "w":
                self.left = _nudge(self.left, 0, sp, 0)
            elif key == "s":
                self.left = _nudge(self.left, 0, -sp, 0)
            elif key == "e":
                self.left = _nudge(self.left, 0, 0, sp)
            elif key == "d":
                self.left = _nudge(self.left, 0, 0, -sp)
            elif key == "i":
                self.right = _nudge(self.right, sp, 0, 0)
            elif key == "k":
                self.right = _nudge(self.right, -sp, 0, 0)
            elif key == "o":
                self.right = _nudge(self.right, 0, sp, 0)
            elif key == "l":
                self.right = _nudge(self.right, 0, -sp, 0)
            elif key == "p":
                self.right = _nudge(self.right, 0, 0, sp)
            elif key in (";", "；"):
                self.right = _nudge(self.right, 0, 0, -sp)
            elif key == "f":
                self.head = _yaw_pose_z(self.head, self.step_yaw)
            elif key == "j":
                self.head = _yaw_pose_z(self.head, -self.step_yaw)

        return buttons

    def consume_reset(self, ref: dict[str, Pose7] | None, head_ref: Pose7 | None) -> None:
        if self._pending_reset:
            self.reset_to_ref(ref, head_ref)
            self._pending_reset = False

    def vr3pt_raw(self) -> dict[str, Pose7]:
        return {"left": _copy_pose(self.left), "right": _copy_pose(self.right), "head": _copy_pose(self.head)}

    def vr3pt_calibrated(self) -> dict[str, Pose7]:
        return self.vr3pt_raw()
