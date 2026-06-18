"""
Quest 3 body reader — test connection and stream body pose data.

Use this to:
  1. Test ADB connection to Quest 3 (run with --test-adb).
  2. Stream body pose in the same format as PicoReader for pico_manager_thread_server.
  3. Stream VR 3-point pose (L-Wrist, R-Wrist, Head) from Meta Quest controllers via meta_quest_teleop.

Expected sample format (compatible with PicoReader):
  body_poses_np: np.ndarray shape (24, 7) — 24 SMPL-like joints, each [x, y, z, qx, qy, qz, qw]
  (Unity frame, scalar-last quaternion)

For source="meta_quest", sample also includes:
  vr_3pt_pose: np.ndarray shape (3, 7) — [x, y, z, qw, qx, qy, qz] per row (robot frame)
  Row 0: Left Wrist, Row 1: Right Wrist, Row 2: Head (default, Quest has no head tracking)

Usage:
  # Test ADB only
  python -m gear_sonic.utils.teleop.readers.quest_reader --test-adb

  # Run reader with synthetic data (no Quest needed) to test pipeline
  python -m gear_sonic.utils.teleop.readers.quest_reader --synthetic

  # Run reader with Meta Quest controllers (meta_quest_teleop)
  python -m gear_sonic.utils.teleop.readers.quest_reader --source meta_quest

  # Run reader using ADB (implement read_quest_body_via_adb for your app)
  python -m gear_sonic.utils.teleop.readers.quest_reader --source adb
"""

import argparse
import os
import subprocess
import sys
import threading
import time

import numpy as np
from scipy.spatial.transform import Rotation as sRot


# -----------------------------------------------------------------------------
# ADB connection test
# -----------------------------------------------------------------------------

def check_adb_connection() -> bool:
    """Check if ADB is available and at least one device is connected."""
    try:
        out = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            print("[QuestReader] adb devices failed")
            return False
        lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
        # First line is "List of devices attached"
        devices = [l for l in lines[1:] if l and not l.startswith("*")]
        if not devices:
            print("[QuestReader] No devices found. Connect Quest 3 via USB and enable USB debugging.")
            return False
        print(f"[QuestReader] ADB devices: {devices}")
        return True
    except FileNotFoundError:
        print("[QuestReader] 'adb' not found. Install Android platform tools.")
        return False
    except subprocess.TimeoutExpired:
        print("[QuestReader] adb devices timed out")
        return False


def ensure_quest_network_adb(ip_address: str, port: int = 5555) -> bool:
    """Connect Quest over WiFi ADB before meta_quest_teleop starts."""
    target = f"{ip_address}:{port}"
    try:
        subprocess.run(["adb", "start-server"], capture_output=True, timeout=10, check=False)
        devices_out = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=5, check=False
        )
        usb_devices = [
            line.split("\t")[0]
            for line in devices_out.stdout.splitlines()[1:]
            if "\tdevice" in line and ":" not in line.split("\t")[0]
        ]
        if usb_devices:
            print(f"[QuestReader] USB device detected ({usb_devices[0]}), enabling adb tcpip {port}...")
            subprocess.run(["adb", "tcpip", str(port)], capture_output=True, timeout=10, check=False)
            time.sleep(1.5)

        connect = subprocess.run(
            ["adb", "connect", target],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        msg = (connect.stdout or "") + (connect.stderr or "")
        if "connected" not in msg.lower() and "already connected" not in msg.lower():
            print(f"[QuestReader] adb connect {target} failed: {msg.strip()}")
            return False

        verify = subprocess.run(
            ["adb", "devices"], capture_output=True, text=True, timeout=5, check=False
        )
        ok = any(
            line.startswith(target) and "\tdevice" in line
            for line in verify.stdout.splitlines()
        )
        if ok:
            print(f"[QuestReader] ADB ready: {target}")
        else:
            print(f"[QuestReader] {target} not listed as device after connect.")
        return ok
    except Exception as e:
        print(f"[QuestReader] ADB setup error: {e}")
        return False


def test_adb():
    """Standalone test: verify ADB and optionally run a shell command."""
    print("Checking ADB connection to Quest 3...")
    if not check_adb_connection():
        sys.exit(1)
    print("ADB connection OK.")
    # Optional: run a simple command on device
    try:
        out = subprocess.run(
            ["adb", "shell", "getprop", "ro.product.model"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            print(f"Device model: {out.stdout.strip()}")
    except Exception as e:
        print(f"Optional shell check: {e}")


# -----------------------------------------------------------------------------
# Default SMPL-like 24-joint pose (identity / T-pose style)
# Used when no real data is available (synthetic mode or fallback).
# -----------------------------------------------------------------------------

def default_smpl_pose_24() -> np.ndarray:
    """Return a default (24, 7) pose: zeros for position, identity quat for rotation."""
    pose = np.zeros((24, 7), dtype=np.float32)
    # Identity quaternion (scalar-last: qx, qy, qz, qw)
    pose[:, 3:7] = [0.0, 0.0, 0.0, 1.0]
    # Optional: set root height
    pose[0, 2] = 1.0
    return pose


# -----------------------------------------------------------------------------
# VR 3-point pose from Meta Quest controllers (meta_quest_teleop)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Head reference frame (row 2 of vr_3pt_pose) — Quest has no head tracking, so we use
# a fixed default. This should match the robot's head position for correct waist/neck
# calibration. Origin: robot pelvis. Frame: X=forward, Y=left, Z=up (ROS convention).
#
# VR_3PT_HEAD_POSITION: [x, y, z] in meters — head position relative to pelvis.
#   Default from C++ zmq_manager.hpp. For G1: ~0.4m above pelvis, slightly forward.
#   To use G1 FK: get_g1_key_frame_poses(robot_model)["torso"] + HEAD_LINK_LENGTH.
#
# VR_3PT_HEAD_ORIENTATION: [qw, qx, qy, qz] — head orientation (identity ≈ looking forward).
# -----------------------------------------------------------------------------
VR_3PT_HEAD_POSITION = np.array([0.0241, -0.0081, 0.4028], dtype=np.float32)
VR_3PT_HEAD_ORIENTATION = np.array([0.9991, 0.011, 0.0402, -0.0002], dtype=np.float32)  # wxyz

# Home positions for calibration (robot frame, meters) — fallback when G1 FK not available
META_QUEST_HOME_LEFT = np.array([0.15, 0.25, 0.45])
META_QUEST_HOME_RIGHT = np.array([0.15, -0.25, 0.45])

# Match SMPL Pico OFFSETS in pico_manager_thread_server.py (wrist link frames)
_QUEST_L_WRIST_ROT_OFFSET = sRot.from_euler("xyz", [90, 0, 0], degrees=True)
_QUEST_R_WRIST_ROT_OFFSET = sRot.from_euler("xyz", [-90, 0, 180], degrees=True)


def _controller_rot_to_wrist(rot_3x3: np.ndarray, hand: str) -> np.ndarray:
    """Map Quest controller orientation to G1 wrist_yaw_link frame."""
    r = sRot.from_matrix(rot_3x3)
    offset = _QUEST_L_WRIST_ROT_OFFSET if hand == "left" else _QUEST_R_WRIST_ROT_OFFSET
    return (r * offset).as_matrix()


def _wrist_4x4_from_controller(pose_4x4: np.ndarray, hand: str) -> np.ndarray:
    out = pose_4x4.copy()
    out[:3, :3] = _controller_rot_to_wrist(pose_4x4[:3, :3], hand)
    return out


def _g1_pose_to_4x4(pos: np.ndarray, quat_wxyz: np.ndarray) -> np.ndarray:
    """Build 4x4 transform from G1 FK pose (position + orientation_wxyz)."""
    # scipy expects [qx, qy, qz, qw]
    q_xyzw = np.array([quat_wxyz[1], quat_wxyz[2], quat_wxyz[3], quat_wxyz[0]], dtype=np.float64)
    R = sRot.from_quat(q_xyzw).as_matrix()
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = pos
    return T


def _compose_pose_4x4(rot_3x3: np.ndarray, pos: np.ndarray) -> np.ndarray:
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = rot_3x3
    out[:3, 3] = pos
    return out


def capture_quest_wrist_calibration(
    home_left: np.ndarray,
    home_right: np.ndarray,
    left_wrist: np.ndarray,
    right_wrist: np.ndarray,
) -> dict[str, np.ndarray]:
    """Store wrist calibration in G1 wrist_yaw_link frame (translation decoupled)."""
    return {
        "home_left": home_left.copy(),
        "home_right": home_right.copy(),
        "calib_left_pos": left_wrist[:3, 3].copy(),
        "calib_right_pos": right_wrist[:3, 3].copy(),
        "left_rot_offset": home_left[:3, :3] @ np.linalg.inv(left_wrist[:3, :3]),
        "right_rot_offset": home_right[:3, :3] @ np.linalg.inv(right_wrist[:3, :3]),
    }


def apply_quest_wrist_calibration(
    calib: dict[str, np.ndarray],
    left_wrist: np.ndarray,
    right_wrist: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply stored calibration to wrist-frame 4x4 poses."""
    left_pos = calib["home_left"][:3, 3] + (left_wrist[:3, 3] - calib["calib_left_pos"])
    right_pos = calib["home_right"][:3, 3] + (right_wrist[:3, 3] - calib["calib_right_pos"])
    left_pose = _compose_pose_4x4(calib["left_rot_offset"] @ left_wrist[:3, :3], left_pos)
    right_pose = _compose_pose_4x4(calib["right_rot_offset"] @ right_wrist[:3, :3], right_pos)
    return left_pose, right_pose


def _matrix_to_quat_wxyz(matrix_3x3: np.ndarray) -> np.ndarray:
    """Convert 3x3 rotation matrix to quaternion [qw, qx, qy, qz] (scalar-first)."""
    r = sRot.from_matrix(matrix_3x3)
    q_xyzw = r.as_quat()  # scipy returns [x, y, z, w]
    return np.array([q_xyzw[3], q_xyzw[0], q_xyzw[1], q_xyzw[2]], dtype=np.float32)


# Permutation matrix kept for legacy APK path only (see QUEST_LEGACY_YZ_SWAP).
_QUEST_TO_ROS_P = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=np.float64)


def _quest_legacy_yz_swap_enabled() -> bool:
    return os.environ.get("QUEST_LEGACY_YZ_SWAP", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _apply_quest_yz_swap(pose_4x4: np.ndarray) -> np.ndarray:
    """
    Legacy axis remap for old teleop APK builds.

    ``meta_quest_teleop.get_hand_controller_transform_ros()`` already converts
    OpenXR → ROS (X=fwd, Y=left, Z=up). Applying this again corrupts rotation
    axes — keep disabled unless QUEST_LEGACY_YZ_SWAP=1.
    """
    out = pose_4x4.copy()
    p = np.array([pose_4x4[2, 3], pose_4x4[0, 3], pose_4x4[1, 3]])
    out[:3, 3] = [p[0], -p[1], -p[2]]
    R = pose_4x4[:3, :3]
    out[:3, :3] = _QUEST_TO_ROS_P @ R @ _QUEST_TO_ROS_P.T
    return out


def _maybe_apply_quest_yz_swap(pose_4x4: np.ndarray) -> np.ndarray:
    if _quest_legacy_yz_swap_enabled():
        return _apply_quest_yz_swap(pose_4x4)
    return pose_4x4.copy()


def _controller_ros_to_wrist_4x4(pose_4x4: np.ndarray, hand: str) -> np.ndarray:
    """Quest controller 4x4 in ROS pelvis frame → G1 wrist_yaw_link 4x4."""
    return _wrist_4x4_from_controller(pose_4x4, hand)


def _trigger_value(reader, hand: str) -> float:
    """Per-hand index trigger [0,1] from leftTrig / rightTrig (Quest APK)."""
    is_left = hand in ("left", "l")
    key = "leftTrig" if is_left else "rightTrig"
    try:
        lock = getattr(reader, "_lock", None)
        buttons = getattr(reader, "_latest_buttons", {})
        if lock is not None:
            with lock:
                val = buttons.get(key, 0.0)
        else:
            val = buttons.get(key, 0.0)
        if isinstance(val, tuple):
            val = float(val[0]) if len(val) > 0 else 0.0
        v = float(val) if val else 0.0
        if v > 0.001:
            return float(np.clip(v, 0.0, 1.0))
    except Exception:
        pass
    try:
        return float(np.clip(float(reader.get_trigger_value(hand)), 0.0, 1.0))
    except Exception:
        return 0.0


def _grip_value(reader, hand: str) -> float:
    """Per-hand grip [0,1] from leftGrip / rightGrip (Quest APK)."""
    is_left = hand in ("left", "l")
    key = "leftGrip" if is_left else "rightGrip"
    try:
        lock = getattr(reader, "_lock", None)
        buttons = getattr(reader, "_latest_buttons", {})
        if lock is not None:
            with lock:
                val = buttons.get(key, 0.0)
        else:
            val = buttons.get(key, 0.0)
        if isinstance(val, tuple):
            val = float(val[0]) if len(val) > 0 else 0.0
        v = float(val) if val else 0.0
        if v > 0.001:
            return float(np.clip(v, 0.0, 1.0))
    except Exception:
        pass
    try:
        return float(np.clip(float(reader.get_grip_value(hand)), 0.0, 1.0))
    except Exception:
        return 0.0


def _slerp_wxyz(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    r0 = sRot.from_quat(q0, scalar_first=True)
    r1 = sRot.from_quat(q1, scalar_first=True)
    key_rots = sRot.concatenate([r0, r1])
    from scipy.spatial.transform import Slerp

    slerp = Slerp([0.0, 1.0], key_rots)
    return slerp(float(np.clip(t, 0.0, 1.0))).as_quat(scalar_first=True)


class _YawSmoother:
    """Low-pass + deadzone for Unity operator view yaw (Quest tracking noise)."""

    def __init__(self, alpha: float = 0.1, deadzone: float = 0.0035):
        self._yaw: float | None = None
        self._alpha = alpha
        self._deadzone = deadzone

    def reset(self) -> None:
        self._yaw = None

    def update(self, yaw: float) -> float:
        yaw = float(yaw)
        if self._yaw is None:
            self._yaw = yaw
            return yaw
        dy = yaw - self._yaw
        dy = (dy + np.pi) % (2 * np.pi) - np.pi
        if abs(dy) < self._deadzone:
            return self._yaw
        self._yaw = float(self._yaw + self._alpha * dy)
        return self._yaw


class _WristPoseSmoother:
    """Smooth calibration overlay wrists only (Unity CALIBRATION mode)."""

    def __init__(self, pos_alpha: float = 0.18, rot_alpha: float = 0.15):
        self._pos: np.ndarray | None = None
        self._quat: np.ndarray | None = None
        self._pos_alpha = pos_alpha
        self._rot_alpha = rot_alpha

    def reset(self) -> None:
        self._pos = None
        self._quat = None

    def update(self, pose_4x4: np.ndarray) -> np.ndarray:
        pos = pose_4x4[:3, 3].copy()
        quat = _matrix_to_quat_wxyz(pose_4x4[:3, :3])
        if self._pos is None:
            self._pos = pos
            self._quat = quat
        else:
            self._pos = self._pos + self._pos_alpha * (pos - self._pos)
            quat = _slerp_wxyz(self._quat, quat, self._rot_alpha)
            self._quat = quat
        out = np.eye(4, dtype=np.float64)
        out[:3, :3] = sRot.from_quat(quat, scalar_first=True).as_matrix()
        out[:3, 3] = self._pos
        return out


def _home_wrist_positions(
    home_left_4x4: np.ndarray | None,
    home_right_4x4: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray]:
    if home_left_4x4 is not None:
        home_l = home_left_4x4[:3, 3].copy()
    else:
        home_l = META_QUEST_HOME_LEFT.copy()
    if home_right_4x4 is not None:
        home_r = home_right_4x4[:3, 3].copy()
    else:
        home_r = META_QUEST_HOME_RIGHT.copy()
    return home_l, home_r


def _quest_pose_relative(current: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """Delta since session origin (same frame as Quest APK output)."""
    return np.linalg.inv(origin) @ current


def _quest_delta_to_pelvis_display(
    rel_4x4: np.ndarray,
    home_pos: np.ndarray,
    home_4x4: np.ndarray | None = None,
) -> np.ndarray:
    """
    Map session-relative Quest motion into G1 pelvis frame for Unity overlay.
    At session origin the displayed wrists sit on G1 FK home (matches ghost).
    """
    out = np.eye(4, dtype=np.float64)
    if home_4x4 is not None:
        out[:3, :3] = home_4x4[:3, :3] @ rel_4x4[:3, :3]
    else:
        out[:3, :3] = rel_4x4[:3, :3]
    out[:3, 3] = home_pos + rel_4x4[:3, 3]
    return out


class _YawSmoother:
    """Low-pass + deadzone for Unity operator yaw (Quest tracking noise)."""

    def __init__(self, alpha: float = 0.12, deadzone_rad: float = 0.004):
        self.alpha = alpha
        self.deadzone_rad = deadzone_rad
        self._yaw: float | None = None

    def reset(self) -> None:
        self._yaw = None

    def update(self, yaw: float) -> float:
        if self._yaw is None:
            self._yaw = float(yaw)
            return self._yaw
        dy = float(yaw) - self._yaw
        dy = (dy + np.pi) % (2 * np.pi) - np.pi
        if abs(dy) < self.deadzone_rad:
            return self._yaw
        self._yaw = self._yaw + self.alpha * dy
        return self._yaw


class _DisplayPoseSmoother:
    """Smooth Quest overlay wrists for Unity calibration UI only."""

    def __init__(self, pos_alpha: float = 0.22, rot_alpha: float = 0.22):
        self.pos_alpha = pos_alpha
        self.rot_alpha = rot_alpha
        self._left: np.ndarray | None = None
        self._right: np.ndarray | None = None

    def reset(self) -> None:
        self._left = None
        self._right = None

    def filter(self, left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        self._left = self._blend(self._left, left)
        self._right = self._blend(self._right, right)
        return self._left.copy(), self._right.copy()

    def _blend(self, prev: np.ndarray | None, cur: np.ndarray) -> np.ndarray:
        if prev is None:
            return cur.copy()
        out = cur.copy()
        out[:3, 3] = prev[:3, 3] + self.pos_alpha * (cur[:3, 3] - prev[:3, 3])
        q_prev = sRot.from_matrix(prev[:3, :3])
        q_cur = sRot.from_matrix(cur[:3, :3])
        delta = q_prev.inv() * q_cur
        q_out = q_prev * sRot.from_rotvec(self.rot_alpha * delta.as_rotvec())
        out[:3, :3] = q_out.as_matrix()
        return out


class _HmdRelSmoother:
    """Low-pass Quest HMD session delta for Unity v2 camera (reduces jitter)."""

    def __init__(
        self,
        pos_alpha: float = 0.18,
        rot_alpha: float = 0.18,
        pos_deadzone_m: float = 0.0015,
    ):
        self.pos_alpha = pos_alpha
        self.rot_alpha = rot_alpha
        self.pos_deadzone_m = pos_deadzone_m
        self._pos: np.ndarray | None = None
        self._quat: np.ndarray | None = None

    def reset(self) -> None:
        self._pos = None
        self._quat = None

    def filter(
        self, rel_pos: list[float], rel_quat: list[float]
    ) -> tuple[list[float], list[float]]:
        p = np.asarray(rel_pos, dtype=np.float64)
        q = np.asarray(rel_quat, dtype=np.float64)
        if self._pos is None:
            self._pos = p.copy()
            self._quat = q.copy()
            return rel_pos, rel_quat
        dp = p - self._pos
        if float(np.linalg.norm(dp)) < self.pos_deadzone_m:
            p = self._pos.copy()
        else:
            p = self._pos + self.pos_alpha * dp
        q = self._quat + self.rot_alpha * (q - self._quat)
        q = q / max(np.linalg.norm(q), 1e-8)
        self._pos = p
        self._quat = q
        return p.tolist(), q.tolist()


def quest_controllers_to_vr_3pt_pose(
    left_4x4: np.ndarray | None,
    right_4x4: np.ndarray | None,
    head_pos: np.ndarray | None = None,
    head_quat_wxyz: np.ndarray | None = None,
    *,
    from_controller_frame: bool = True,
) -> np.ndarray:
    """
    Convert Meta Quest controller 4x4 poses to VR 3-point pose for SONIC.

    Args:
        left_4x4: 4x4 transform for left controller (ROS frame = robot frame)
        right_4x4: 4x4 transform for right controller
        head_pos: Optional head position [x,y,z]. Default: VR_3PT_HEAD_POSITION
        head_quat_wxyz: Optional head quat [qw,qx,qy,qz]. Default: VR_3PT_HEAD_ORIENTATION
        from_controller_frame: When True (default), apply Quest controller → G1 wrist
            rotation offsets. Set False for poses already in G1 wrist frame (e.g. after
            FK-based calibration or pelvis-overlay display transforms).

    Returns:
        vr_3pt_pose: np.ndarray shape (3, 7) — each row [x, y, z, qw, qx, qy, qz]
        Row 0: Left Wrist, Row 1: Right Wrist, Row 2: Head (robot head frame, see VR_3PT_HEAD_*)
    """

    def _wrist_pose(pose_4x4: np.ndarray, hand: str) -> np.ndarray:
        if from_controller_frame:
            return _wrist_4x4_from_controller(pose_4x4, hand)
        return pose_4x4

    out = np.zeros((3, 7), dtype=np.float32)
    head_pos = head_pos if head_pos is not None else VR_3PT_HEAD_POSITION
    head_quat = head_quat_wxyz if head_quat_wxyz is not None else VR_3PT_HEAD_ORIENTATION

    # Row 0, 1: controller poses (wrists). Row 2: head — fixed default when Quest has no head tracking.
    # Head frame origin should be at robot head for correct waist/neck calibration.
    if left_4x4 is not None:
        lw = _wrist_pose(left_4x4, "left")
        out[0, :3] = lw[:3, 3]
        out[0, 3:7] = _matrix_to_quat_wxyz(lw[:3, :3])
    else:
        out[0, :3] = META_QUEST_HOME_LEFT
        out[0, 3:7] = [1.0, 0.0, 0.0, 0.0]

    if right_4x4 is not None:
        rw = _wrist_pose(right_4x4, "right")
        out[1, :3] = rw[:3, 3]
        out[1, 3:7] = _matrix_to_quat_wxyz(rw[:3, :3])
    else:
        out[1, :3] = META_QUEST_HOME_RIGHT
        out[1, 3:7] = [1.0, 0.0, 0.0, 0.0]

    # Row 2: fixed robot head for SONIC planner / MuJoCo — never Quest HMD rotation.
    out[2, :3] = VR_3PT_HEAD_POSITION
    out[2, 3:7] = VR_3PT_HEAD_ORIENTATION
    return out


def _quest_controller_pose_ros(reader, hand: str) -> np.ndarray | None:
    """Read controller 4x4 from meta_quest_teleop (already ROS: X=fwd, Y=left, Z=up)."""
    raw = reader.get_hand_controller_transform_ros(hand)
    if raw is None:
        return None
    return _maybe_apply_quest_yz_swap(raw)


def _head_transform_ros(reader) -> np.ndarray | None:
    """HMD 4x4 in ROS frame if teleop APK publishes transform key 'h'."""
    Q = sRot.from_quat([0.5, -0.5, -0.5, 0.5])
    T_static = np.eye(4)
    T_static[:3, :3] = Q.as_matrix()
    lock = getattr(reader, "_lock", None)
    transforms = getattr(reader, "_latest_transforms", {})
    if lock is not None:
        with lock:
            items = list(transforms.items())
    else:
        items = list(transforms.items())
    for key, mat in items:
        if key.lower() != "h":
            continue
        head = T_static @ np.asarray(mat, dtype=np.float64).copy()
        return _maybe_apply_quest_yz_swap(head)
    return None


def _pelvis_yaw_from_rotation(R: np.ndarray) -> float:
    """Extract yaw about pelvis Z from a delta rotation (MuJoCo X-forward convention)."""
    forward = R @ np.array([1.0, 0.0, 0.0], dtype=np.float64)
    return float(np.arctan2(forward[1], forward[0]))


def _average_yaw(yaw_a: float, yaw_b: float) -> float:
    return float(np.arctan2(np.sin(yaw_a) + np.sin(yaw_b), np.cos(yaw_a) + np.cos(yaw_b)))


def _unity_head_quat_from_yaw_delta(base_rot: sRot, R_delta: np.ndarray) -> list[float]:
    yaw = _pelvis_yaw_from_rotation(R_delta)
    out = base_rot * sRot.from_euler("z", yaw, degrees=False)
    return _matrix_to_quat_wxyz(out.as_matrix()).tolist()


def unity_head_pose_from_quest(
    left_4x4: np.ndarray | None,
    right_4x4: np.ndarray | None,
    *,
    rel_left: np.ndarray | None = None,
    rel_right: np.ndarray | None = None,
    rel_head: np.ndarray | None = None,
    head_4x4: np.ndarray | None = None,
    hmd_calib_inv: np.ndarray | None = None,
    ctrl_left_inv: np.ndarray | None = None,
    ctrl_right_inv: np.ndarray | None = None,
    use_calibrated_view: bool = False,
    yaw_smoother: _YawSmoother | None = None,
) -> dict[str, list[float]]:
    """Unity operator camera — yaw-only view direction; position is fixed (Unity uses MuJoCo head FK)."""
    base_rot = sRot.from_quat(VR_3PT_HEAD_ORIENTATION, scalar_first=True)
    pos = VR_3PT_HEAD_POSITION.tolist()

    if head_4x4 is not None and hmd_calib_inv is not None:
        R_hmd = hmd_calib_inv @ np.asarray(head_4x4[:3, :3], dtype=np.float64)
        yaw = _pelvis_yaw_from_rotation(R_hmd)
        if yaw_smoother is not None:
            yaw = yaw_smoother.update(yaw)
        quat = _unity_head_quat_from_yaw_delta(
            base_rot, sRot.from_euler("z", yaw, degrees=False).as_matrix()
        )
        return {"p": pos, "q": quat}

    yaw: float | None = None
    if head_4x4 is not None and rel_head is not None:
        yaw = _pelvis_yaw_from_rotation(rel_head[:3, :3])
    elif (
        use_calibrated_view
        and left_4x4 is not None
        and right_4x4 is not None
        and ctrl_left_inv is not None
        and ctrl_right_inv is not None
    ):
        R_l = ctrl_left_inv @ np.asarray(left_4x4[:3, :3], dtype=np.float64)
        R_r = ctrl_right_inv @ np.asarray(right_4x4[:3, :3], dtype=np.float64)
        yaw = _average_yaw(_pelvis_yaw_from_rotation(R_l), _pelvis_yaw_from_rotation(R_r))
    elif rel_left is not None and rel_right is not None:
        yaw = _average_yaw(
            _pelvis_yaw_from_rotation(rel_left[:3, :3]),
            _pelvis_yaw_from_rotation(rel_right[:3, :3]),
        )

    if yaw is None:
        return {"p": pos, "q": VR_3PT_HEAD_ORIENTATION.tolist()}

    if yaw_smoother is not None:
        yaw = yaw_smoother.update(yaw)

    quat = _unity_head_quat_from_yaw_delta(
        base_rot,
        sRot.from_euler("z", yaw, degrees=False).as_matrix(),
    )
    return {"p": pos, "q": quat}


def _quat_multiply_wxyz(q1: list[float], q2: list[float]) -> list[float]:
    """Hamilton product, scalar-first [w,x,y,z]."""
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return [
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ]


def hmd_rel_from_quest(
    head_4x4: np.ndarray | None,
    rel_head: np.ndarray | None,
    hmd_calib_rot: np.ndarray | None = None,
) -> tuple[list[float], list[float]]:
    """Session-relative HMD delta for Unity v2 camera (MuJoCo pelvis frame)."""
    if rel_head is None:
        return [0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]
    rel_pos = rel_head[:3, 3].astype(np.float64).tolist()
    if hmd_calib_rot is not None and head_4x4 is not None:
        R_rel = np.linalg.inv(hmd_calib_rot) @ np.asarray(head_4x4[:3, :3], dtype=np.float64)
    else:
        R_rel = rel_head[:3, :3]
    return rel_pos, _matrix_to_quat_wxyz(R_rel).tolist()


def build_hmd_view_pose(
    robot_head_p: list[float],
    robot_head_q: list[float],
    hmd_rel_pos: list[float] | None,
    hmd_rel_quat: list[float] | None,
) -> dict[str, list[float]]:
    """
    Unity v2 operator camera in MuJoCo pelvis frame.
    Anchor = robot_actual.head FK; overlay Quest HMD session delta.
    """
    pos = [float(robot_head_p[i]) + float((hmd_rel_pos or [0, 0, 0])[i]) for i in range(3)]
    quat = list(robot_head_q)
    if hmd_rel_quat is not None and len(hmd_rel_quat) >= 4:
        quat = _quat_multiply_wxyz(list(robot_head_q), list(hmd_rel_quat))
    return {"p": pos, "q": quat}


def unity_head_pose_dict(
    left_4x4: np.ndarray | None,
    right_4x4: np.ndarray | None,
    head_4x4: np.ndarray | None = None,
    hmd_calib_inv: np.ndarray | None = None,
    ctrl_left_inv: np.ndarray | None = None,
    ctrl_right_inv: np.ndarray | None = None,
) -> dict[str, list[float]]:
    """Backward-compatible wrapper."""
    return unity_head_pose_from_quest(
        left_4x4,
        right_4x4,
        head_4x4=head_4x4,
        hmd_calib_inv=hmd_calib_inv,
        ctrl_left_inv=ctrl_left_inv,
        ctrl_right_inv=ctrl_right_inv,
        use_calibrated_view=ctrl_left_inv is not None and ctrl_right_inv is not None,
    )


def estimate_head_pose_ros(
    left_4x4: np.ndarray | None,
    right_4x4: np.ndarray | None,
    head_4x4: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Unity operator view: prefer HMD transform, else estimate from both controllers."""
    if head_4x4 is not None:
        return head_4x4[:3, 3].astype(np.float32), _matrix_to_quat_wxyz(head_4x4[:3, :3])
    if left_4x4 is None or right_4x4 is None:
        return VR_3PT_HEAD_POSITION.copy(), VR_3PT_HEAD_ORIENTATION.copy()

    lp = left_4x4[:3, 3]
    rp = right_4x4[:3, 3]
    mid = (lp + rp) * 0.5
    forward = left_4x4[:3, 0] + right_4x4[:3, 0]
    fn = np.linalg.norm(forward)
    if fn < 1e-6:
        forward = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    else:
        forward = forward / fn
    up = left_4x4[:3, 2] + right_4x4[:3, 2]
    un = np.linalg.norm(up)
    if un < 1e-6:
        up = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    else:
        up = up / un
    head_pos = mid + 0.14 * up + 0.04 * forward
    y_axis = np.cross(up, forward)
    yn = np.linalg.norm(y_axis)
    if yn < 1e-6:
        return head_pos.astype(np.float32), VR_3PT_HEAD_ORIENTATION.copy()
    y_axis = y_axis / yn
    up = np.cross(forward, y_axis)
    R = np.column_stack([forward, y_axis, up])
    return head_pos.astype(np.float32), _matrix_to_quat_wxyz(R)


# -----------------------------------------------------------------------------
# Read body from Quest via ADB (stub — implement with your app)
# -----------------------------------------------------------------------------

def read_quest_body_via_adb() -> np.ndarray | None:
    """
    Read body pose from Quest 3 via ADB.

    Implement according to your setup, for example:
      - Quest app writes pose to /sdcard/body_pose.bin or .json; adb pull or exec-out cat
      - Quest app opens TCP server; adb forward tcp:LOCAL tcp:REMOTE, then socket read
      - Your PC script receives from Quest app over ADB or network

    Returns:
      np.ndarray shape (N, 7) with [x, y, z, qx, qy, qz, qw] per joint (Quest format).
      Or None if no data this frame.
    """
    # Stub: no real read yet
    return None


def quest_joints_to_smpl_24(quest_joints: np.ndarray) -> np.ndarray:
    """
    Map Quest joint array to SMPL-like 24 joints.

    If quest_joints already has 24 rows, use them (optionally reorder).
    If Quest uses 70 joints (Meta IOBT), map key indices to SMPL 24.
    """
    if quest_joints is None or quest_joints.size == 0:
        return default_smpl_pose_24()

    n = quest_joints.shape[0]
    smpl = np.zeros((24, 7), dtype=np.float32)
    smpl[:, 3:7] = [0.0, 0.0, 0.0, 1.0]

    if n >= 24:
        smpl[:24] = quest_joints[:24]
        return smpl

    # Minimal mapping for 70-joint Meta format (indices to adjust per Meta docs)
    # SMPL: 0=root, 12=neck, 22=left_wrist, 23=right_wrist
    meta_to_smpl = {
        0: 0,   # Root
        7: 12,  # Neck (example)
        24: 22, # Left wrist (example)
        25: 23, # Right wrist (example)
    }
    for meta_idx, smpl_idx in meta_to_smpl.items():
        if meta_idx < n:
            smpl[smpl_idx] = quest_joints[meta_idx]
    return smpl


# -----------------------------------------------------------------------------
# QuestReader — same interface as PicoReader for drop-in use
# -----------------------------------------------------------------------------

class QuestReader:
    """
    Background reader that produces body pose samples compatible with PicoReader.

    Use source="synthetic" to emit dummy poses (for testing pipeline without Quest).
    Use source="meta_quest" to read controller poses via meta_quest_teleop (VR 3-point format).
    Use source="keyboard" for WSL keyboard teleop (see keyboard_quest_input.py).
    Use source="adb" to read from Quest via ADB (implement read_quest_body_via_adb).
    """

    def __init__(
        self,
        source: str = "synthetic",
        max_queue_size: int = 15,
        ip_address: str | None = None,
        home_left_pose: np.ndarray | None = None,
        home_right_pose: np.ndarray | None = None,
        keyboard_state_file: str | None = "/tmp/sonic_keyboard_sample.json",
    ):
        """
        Args:
            home_left_pose: 4x4 transform for left wrist reference (G1 FK default).
                If None, uses META_QUEST_HOME_LEFT (position only).
            home_right_pose: 4x4 transform for right wrist reference (G1 FK default).
                If None, uses META_QUEST_HOME_RIGHT (position only).
        """
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._latest = None
        self._lock = threading.Lock()
        self._source = source.lower()
        self._fps_ema = 0.0
        self._last_stamp_ns = None
        self._frame_count = 0
        self._ip_address = ip_address
        self._home_left_pose = home_left_pose
        self._home_right_pose = home_right_pose
        if self._source == "meta_quest" and keyboard_state_file == "/tmp/sonic_keyboard_sample.json":
            keyboard_state_file = "/tmp/sonic_quest_sample.json"
        self._keyboard_state_file = keyboard_state_file
        self._sample_export_file = (
            keyboard_state_file if self._source in ("meta_quest", "keyboard") else None
        )
        self._export_extra: dict = {}
        self._export_extra_lock = threading.Lock()
        self._kb = None
        self._last_json_export_t = 0.0

    def set_export_extra(self, fields: dict | None) -> None:
        """Merge fields into JSON export (e.g. manager stream mode for Unity bridge)."""
        with self._export_extra_lock:
            self._export_extra = dict(fields) if fields else {}

    def _merged_export_sample(self, sample: dict) -> dict:
        with self._export_extra_lock:
            extra = dict(self._export_extra)
        if not extra:
            return sample
        return {**sample, **extra}

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)
        if hasattr(self, "_kb") and self._kb is not None:
            try:
                self._kb.disable_stdin()
            except Exception:
                pass
        if hasattr(self, "_meta_quest_reader") and self._meta_quest_reader is not None:
            try:
                self._meta_quest_reader.stop()
            except Exception:
                pass

    def get_latest(self):
        with self._lock:
            return self._latest

    def reset_calibration(self) -> None:
        """Clear wrist calibration so operator must press B again."""
        self._wrist_calib = None
        self._is_calibrated = False
        self._hmd_calib_rot = None
        self._view_calib_left_inv = None
        self._view_calib_right_inv = None
        self._session_origin_left = None
        self._session_origin_right = None
        self._session_origin_head = None
        for attr in ("_view_yaw_smoother", "_display_smoother", "_hmd_rel_smoother"):
            smoother = getattr(self, attr, None)
            if smoother is not None and hasattr(smoother, "reset"):
                smoother.reset()
        print("[QuestReader] Calibration cleared — press B to re-calibrate.")

    def calibrate_now(self) -> bool:
        """Capture Quest wrist offsets vs G1 FK default (T3 B button)."""
        if not hasattr(self, "_meta_quest_reader") or self._meta_quest_reader is None:
            print("[QuestReader] Cannot calibrate: MetaQuestReader not connected.")
            return False
        reader = self._meta_quest_reader
        left_raw = _quest_controller_pose_ros(reader, "left")
        right_raw = _quest_controller_pose_ros(reader, "right")
        head_T = _head_transform_ros(reader)
        if left_raw is None or right_raw is None:
            print("[QuestReader] Cannot calibrate: controller transforms unavailable.")
            return False
        try:
            if self._home_left_pose is not None and self._home_right_pose is not None:
                home_left = self._home_left_pose.copy()
                home_right = self._home_right_pose.copy()
                ref_source = "G1 FK default"
            else:
                home_left = np.eye(4)
                home_left[:3, 3] = META_QUEST_HOME_LEFT
                home_right = np.eye(4)
                home_right[:3, 3] = META_QUEST_HOME_RIGHT
                ref_source = "META_QUEST_HOME"
            self._wrist_calib = capture_quest_wrist_calibration(
                home_left,
                home_right,
                _controller_ros_to_wrist_4x4(left_raw, "left"),
                _controller_ros_to_wrist_4x4(right_raw, "right"),
            )
            self._is_calibrated = True
            if head_T is not None:
                self._hmd_calib_rot = np.asarray(head_T[:3, :3], dtype=np.float64).copy()
            left_w = _controller_ros_to_wrist_4x4(left_raw, "left")
            right_w = _controller_ros_to_wrist_4x4(right_raw, "right")
            self._view_calib_left_inv = np.linalg.inv(left_w[:3, :3])
            self._view_calib_right_inv = np.linalg.inv(right_w[:3, :3])
            self._session_origin_left = left_w.copy()
            self._session_origin_right = right_w.copy()
            if head_T is not None:
                self._session_origin_head = head_T.copy()
            self._view_yaw_smoother.reset()
            self._display_smoother.reset()
            self._hmd_rel_smoother.reset()
            print(f"[QuestReader] Calibration complete (B, ref={ref_source}).")
            return True
        except np.linalg.LinAlgError:
            print("[QuestReader] Calibration failed (singular transform).")
            return False

    def _run_meta_quest(self, t_realtime: float, t_monotonic: float, stamp_ns: int, device_dt: float):
        """Read from MetaQuestReader and produce vr_3pt_pose sample."""
        if not hasattr(self, "_meta_quest_reader") or self._meta_quest_reader is None:
            if getattr(self, "_meta_quest_init_failed", False):
                return None
            try:
                from meta_quest_teleop.reader import MetaQuestReader  # pyright: ignore[reportMissingImports]

                if self._ip_address:
                    now = time.monotonic()
                    last = getattr(self, "_last_adb_attempt", 0.0)
                    if now - last >= 5.0:
                        self._last_adb_attempt = now
                        if not ensure_quest_network_adb(self._ip_address):
                            if not getattr(self, "_adb_unreachable_logged", False):
                                print(
                                    "[QuestReader] Quest ADB unreachable. Steps:\n"
                                    "  1) USB connect Quest, allow USB debugging\n"
                                    "  2) adb devices  (must show device)\n"
                                    "  3) adb tcpip 5555\n"
                                    "  4) adb connect <quest-ip>:5555\n"
                                    "  5) On Quest: open com.rail.oculus.teleop app\n"
                                    "  (will retry ADB every 5s — ABXY 无效直到连上)"
                                )
                                self._adb_unreachable_logged = True
                            return None
                    else:
                        return None
                    self._adb_unreachable_logged = False

                self._meta_quest_reader = MetaQuestReader(
                    ip_address=self._ip_address,
                    run=True,
                )
                self._wrist_calib = None
                self._is_calibrated = False
                self._hmd_calib_rot = None
                self._view_calib_left_inv = None
                self._view_calib_right_inv = None
                self._session_origin_left = None
                self._session_origin_right = None
                self._session_origin_head = None
                self._view_yaw_smoother = _YawSmoother()
                self._display_smoother = _DisplayPoseSmoother()
                self._hmd_rel_smoother = _HmdRelSmoother()
                print("[QuestReader] MetaQuestReader started. 腕校准: T3 按 B（扳机仅手指，不校准）。")
            except ImportError as e:
                print(f"[QuestReader] meta_quest_teleop not installed: {e}")
                self._meta_quest_init_failed = True
                return None
            except (SystemExit, RecursionError, RuntimeError):
                print("[QuestReader] MetaQuestReader failed (no device?). Connect Quest via USB/WiFi.")
                self._meta_quest_init_failed = True
                self._meta_quest_reader = None
                return None

        reader = self._meta_quest_reader
        left_raw = _quest_controller_pose_ros(reader, "left")
        right_raw = _quest_controller_pose_ros(reader, "right")

        def _btn(name: str) -> bool:
            try:
                return bool(reader.get_button_state(name))
            except Exception:
                return False

        left_menu = _btn("leftMenu") or _btn("menu")
        head_T = _head_transform_ros(reader)

        if left_raw is None or right_raw is None:
            return None

        left_wrist = _controller_ros_to_wrist_4x4(left_raw, "left")
        right_wrist = _controller_ros_to_wrist_4x4(right_raw, "right")

        if getattr(self, "_session_origin_left", None) is None:
            self._session_origin_left = left_wrist.copy()
            self._session_origin_right = right_wrist.copy()
            if head_T is not None:
                self._session_origin_head = head_T.copy()
            print(
                "[QuestReader] Session origin captured — Quest room coords mapped to G1 pelvis overlay."
            )

        rel_head = None
        if head_T is not None and getattr(self, "_session_origin_head", None) is not None:
            rel_head = _quest_pose_relative(head_T, self._session_origin_head)

        if self._home_left_pose is not None and self._home_right_pose is not None:
            home_left_4 = self._home_left_pose
            home_right_4 = self._home_right_pose
        else:
            home_left_4 = np.eye(4)
            home_left_4[:3, 3] = META_QUEST_HOME_LEFT
            home_right_4 = np.eye(4)
            home_right_4[:3, 3] = META_QUEST_HOME_RIGHT

        home_lp, home_rp = _home_wrist_positions(home_left_4, home_right_4)
        rel_l = _quest_pose_relative(left_wrist, self._session_origin_left)
        rel_r = _quest_pose_relative(right_wrist, self._session_origin_right)
        left_display = _quest_delta_to_pelvis_display(rel_l, home_lp, home_left_4)
        right_display = _quest_delta_to_pelvis_display(rel_r, home_rp, home_right_4)
        left_display, right_display = self._display_smoother.filter(left_display, right_display)

        hmd_rel_pos, hmd_rel_quat = hmd_rel_from_quest(
            head_T,
            rel_head,
            getattr(self, "_hmd_calib_rot", None),
        )
        hmd_rel_pos, hmd_rel_quat = self._hmd_rel_smoother.filter(hmd_rel_pos, hmd_rel_quat)

        left_axis = reader.get_joystick_value("left")
        right_axis = reader.get_joystick_value("right")
        left_axis = (float(left_axis[0]), float(left_axis[1])) if len(left_axis) >= 2 else (0.0, 0.0)
        right_axis = (float(right_axis[0]), float(right_axis[1])) if len(right_axis) >= 2 else (0.0, 0.0)

        base = {
            "timestamp_realtime": t_realtime,
            "timestamp_monotonic": t_monotonic,
            "timestamp_ns": stamp_ns,
            "dt": device_dt,
            "fps": self._fps_ema,
            "quest_calibrated": bool(self._is_calibrated),
            "button_a": _btn("A"),
            "button_b": _btn("B"),
            "button_x": _btn("X"),
            "button_y": _btn("Y"),
            "left_trigger": _trigger_value(reader, "left"),
            "right_trigger": _trigger_value(reader, "right"),
            "left_grip": _grip_value(reader, "left"),
            "right_grip": _grip_value(reader, "right"),
            "left_axis": left_axis,
            "right_axis": right_axis,
            "left_axis_click": _btn("LJ"),
            "right_axis_click": _btn("RJ"),
            "left_menu_button": _btn("leftMenu") or _btn("menu") or False,
            "unity_head_pose": unity_head_pose_from_quest(
                left_raw,
                right_raw,
                rel_left=rel_l,
                rel_right=rel_r,
                rel_head=rel_head,
                head_4x4=head_T,
                hmd_calib_inv=(
                    np.linalg.inv(self._hmd_calib_rot)
                    if getattr(self, "_hmd_calib_rot", None) is not None
                    else None
                ),
                ctrl_left_inv=getattr(self, "_view_calib_left_inv", None),
                ctrl_right_inv=getattr(self, "_view_calib_right_inv", None),
                use_calibrated_view=bool(
                    self._is_calibrated
                    and getattr(self, "_view_calib_left_inv", None) is not None
                    and head_T is None
                ),
                yaw_smoother=self._view_yaw_smoother,
            ),
            "hmd_rel_pos": hmd_rel_pos,
            "hmd_rel_quat": hmd_rel_quat,
        }

        vr_3pt_raw = quest_controllers_to_vr_3pt_pose(
            left_display, right_display, from_controller_frame=False
        )

        # Uncalibrated: Unity alignment only (no vr_3pt_pose for manager).
        if not self._is_calibrated or self._wrist_calib is None:
            base["vr_3pt_raw_pose"] = vr_3pt_raw
            return base

        left_pose, right_pose = apply_quest_wrist_calibration(
            self._wrist_calib, left_wrist, right_wrist
        )
        vr_3pt_pose = quest_controllers_to_vr_3pt_pose(
            left_pose, right_pose, from_controller_frame=False
        )

        body_poses_np = default_smpl_pose_24()
        body_poses_np[22, :3] = left_pose[:3, 3]
        body_poses_np[23, :3] = right_pose[:3, 3]
        q_l = _matrix_to_quat_wxyz(left_pose[:3, :3])
        q_r = _matrix_to_quat_wxyz(right_pose[:3, :3])
        body_poses_np[22, 3:7] = [q_l[1], q_l[2], q_l[3], q_l[0]]  # wxyz -> xyzw
        body_poses_np[23, 3:7] = [q_r[1], q_r[2], q_r[3], q_r[0]]

        base["body_poses_np"] = body_poses_np
        base["vr_3pt_pose"] = vr_3pt_pose
        base["vr_3pt_raw_pose"] = vr_3pt_raw
        return base

    def _run_keyboard(self, t_realtime: float, t_monotonic: float, stamp_ns: int, device_dt: float):
        if self._kb is None:
            from gear_sonic.utils.teleop.readers.keyboard_quest_input import KeyboardQuestInput

            self._kb = KeyboardQuestInput(state_file=self._keyboard_state_file)
            self._kb.set_home_reference(self._home_left_pose, self._home_right_pose)
            self._kb.init_poses(self._home_left_pose, self._home_right_pose)
            if not self._kb.enable_stdin():
                return None
        return self._kb.build_sample(
            stamp_ns=stamp_ns,
            device_dt=device_dt,
            fps=self._fps_ema,
            quest_controllers_to_vr_3pt_pose=quest_controllers_to_vr_3pt_pose,
        )

    def _run(self):
        last_report = time.time()
        while not self._stop.is_set():
            t_realtime = time.time()
            t_monotonic = time.monotonic()
            stamp_ns = int(t_monotonic * 1e9)
            prev_stamp_ns = self._last_stamp_ns
            device_dt = (stamp_ns - prev_stamp_ns) * 1e-9 if prev_stamp_ns is not None else 0.0
            if device_dt > 0:
                inst = 1.0 / device_dt
                self._fps_ema = inst if self._fps_ema == 0.0 else (0.9 * self._fps_ema + 0.1 * inst)
            self._last_stamp_ns = stamp_ns

            sample = None
            if self._source == "synthetic":
                body_poses_np = default_smpl_pose_24()
                self._frame_count += 1
                body_poses_np[0, 0] = 0.1 * np.sin(self._frame_count * 0.1)
                sample = {
                    "body_poses_np": body_poses_np,
                    "timestamp_realtime": t_realtime,
                    "timestamp_monotonic": t_monotonic,
                    "timestamp_ns": stamp_ns,
                    "dt": device_dt,
                    "fps": self._fps_ema,
                }
            elif self._source == "meta_quest":
                sample = self._run_meta_quest(t_realtime, t_monotonic, stamp_ns, device_dt)
            elif self._source == "keyboard":
                sample = self._run_keyboard(t_realtime, t_monotonic, stamp_ns, device_dt)
            elif self._source == "adb":
                raw = read_quest_body_via_adb()
                body_poses_np = quest_joints_to_smpl_24(raw) if raw is not None else None
                if body_poses_np is not None:
                    sample = {
                        "body_poses_np": body_poses_np,
                        "timestamp_realtime": t_realtime,
                        "timestamp_monotonic": t_monotonic,
                        "timestamp_ns": stamp_ns,
                        "dt": device_dt,
                        "fps": self._fps_ema,
                    }

            if sample is not None:
                with self._lock:
                    self._latest = sample
                if self._source == "meta_quest" and self._sample_export_file:
                    if t_monotonic - self._last_json_export_t >= 0.05:
                        from gear_sonic.utils.teleop.readers.keyboard_quest_input import write_sample_json

                        write_sample_json(
                            self._sample_export_file,
                            self._merged_export_sample(sample),
                            log_prefix="QuestReader",
                        )
                        self._last_json_export_t = t_monotonic

            if time.time() - last_report >= 5.0:
                print(f"[QuestReader] source={self._source} fps={self._fps_ema:.2f}")
                last_report = time.time()

            time.sleep(0.008)


# -----------------------------------------------------------------------------
# CLI for testing connection and reader
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quest 3 reader — test ADB or run reader")
    parser.add_argument("--test-adb", action="store_true", help="Only test ADB connection and exit")
    parser.add_argument("--synthetic", action="store_true", help="Run reader with synthetic data (no Quest)")
    parser.add_argument(
        "--source",
        choices=["adb", "synthetic", "meta_quest", "keyboard"],
        default="synthetic",
        help="Reader source (meta_quest uses meta_quest_teleop)",
    )
    parser.add_argument("--ip-address", type=str, default=None, help="Quest IP for WiFi (meta_quest only)")
    parser.add_argument("--duration", type=float, default=10.0, help="Run reader for N seconds (default 10)")
    args = parser.parse_args()

    if args.test_adb:
        test_adb()
        return

    source = "synthetic" if args.synthetic else args.source
    print(f"Starting QuestReader (source={source}) for {args.duration}s...")
    reader = QuestReader(
        source=source,
        ip_address=args.ip_address,
    )
    reader.start()
    try:
        time.sleep(args.duration)
        sample = reader.get_latest()
        if sample is not None:
            print(f"Last sample: body_poses_np shape {sample['body_poses_np'].shape}, fps={sample['fps']:.2f}")
            if "vr_3pt_pose" in sample:
                v = sample["vr_3pt_pose"]
                print(f"  vr_3pt_pose shape {v.shape}: L={v[0,:3]}, R={v[1,:3]}, H={v[2,:3]}")
    finally:
        reader.stop()
    print("Done.")


if __name__ == "__main__":
    main()
