"""Main bridge: QuestReader + MuJoCo ZMQ feedback → UDP (Path B state sync)."""

from __future__ import annotations

import argparse
import math
import socket
import time

import numpy as np

from sonic_bridge.alignment import alignment_score, alignment_score_pose7, vr3pt_rows_to_poses
from sonic_bridge.g1_fk import (
    FIXED_VR3PT_HEAD,
    default_body_q,
    d435_pose,
    keyframe_poses,
    standing_body_q,
    synthetic_body_q,
    visual_link_poses,
)
from sonic_bridge.g1_hand_display import hand_display_parts
from sonic_bridge.hand_ik import compute_hand_joints
from sonic_bridge.protocol import BridgeState, Pose7, encode_packet
from sonic_bridge.keyboard_teleop import KeyboardTeleop
from sonic_bridge.quest_controls import QuestPipelineControls
from sonic_bridge.recorder import TrajectoryRecorder
from sonic_bridge.scene_layout import SCENE_NAME, pelvis_world_packet, scene_objects_packet
from sonic_bridge.tcp_relay import TcpLineRelay
from sonic_bridge.zmq_feedback import MujocoFeedbackReader


def _load_g1_home_4x4():
    from gear_sonic.utils.teleop.readers.quest_reader import _g1_pose_to_4x4

    try:
        poses = keyframe_poses(default_body_q())
        home_l = _g1_pose_to_4x4(
            np.array(poses["left"].p, dtype=np.float64),
            np.array(poses["left"].q, dtype=np.float64),
        )
        home_r = _g1_pose_to_4x4(
            np.array(poses["right"].p, dtype=np.float64),
            np.array(poses["right"].q, dtype=np.float64),
        )
        return home_l, home_r, poses
    except Exception as e:
        print(f"[Bridge] G1 FK unavailable ({e}), using fallback home wrists")
        home_l = np.eye(4)
        home_l[:3, 3] = [0.15, 0.25, 0.45]
        home_r = np.eye(4)
        home_r[:3, 3] = [0.15, -0.25, 0.45]
        return home_l, home_r, None


def _pose7_from_4x4(T: np.ndarray) -> Pose7:
    from scipy.spatial.transform import Rotation as sRot

    q_xyzw = sRot.from_matrix(T[:3, :3]).as_quat()
    q = [float(q_xyzw[3]), float(q_xyzw[0]), float(q_xyzw[1]), float(q_xyzw[2])]
    p = [float(T[0, 3]), float(T[1, 3]), float(T[2, 3])]
    return Pose7(p=p, q=q)


def _static_g1_ref(home_l, home_r, home_frames) -> dict[str, Pose7]:
    return {
        "left": _pose7_from_4x4(home_l) if home_frames is None else home_frames["left"],
        "right": _pose7_from_4x4(home_r) if home_frames is None else home_frames["right"],
    }


def _sync_g1_ref_from_mujoco(state: BridgeState, static_ref: dict[str, Pose7]) -> None:
    """Calibration ghosts = static FK home; teleop can follow sim measured wrists."""
    teleop = state.display_mode == "TELEOP" and state.calibrated
    ra = state.robot_actual
    if teleop and ra and ra.get("left") and ra.get("right"):
        state.g1_ref = {"left": ra["left"], "right": ra["right"]}
    else:
        state.g1_ref = dict(static_ref)


def _vr_dict_from_rows(v: np.ndarray) -> dict[str, Pose7]:
    return {
        "left": Pose7.from_vr_row(v[0]),
        "right": Pose7.from_vr_row(v[1]),
        "head": FIXED_VR3PT_HEAD,
    }


def _unity_head_from_sample(sample: dict | None) -> Pose7 | None:
    if not sample:
        return None
    uh = sample.get("unity_head_pose")
    if uh is None:
        return None
    if isinstance(uh, dict) and "p" in uh and "q" in uh:
        return Pose7(p=list(uh["p"]), q=list(uh["q"]))
    return None


def _refresh_visual_links_with_hands(state: BridgeState, q: np.ndarray | None) -> None:
    """Re-FK G1 mesh including Dex3 finger joints from trigger/grip."""
    try:
        if q is not None or state.left_hand_joints or state.right_hand_joints:
            state.visual_links = visual_link_poses(
                q,
                left_hand=state.left_hand_joints,
                right_hand=state.right_hand_joints,
            )
        if state.visual_links:
            state.left_hand_display = hand_display_parts(state.visual_links, "left")
            state.right_hand_display = hand_display_parts(state.visual_links, "right")
    except Exception as e:
        print(f"[Bridge] visual_links hand FK failed: {e}")


def _alignment_from_vr_rows(
    v: np.ndarray,
    ref_left: np.ndarray,
    ref_right: np.ndarray,
) -> float:
    left_T, right_T = vr3pt_rows_to_poses(v)
    return alignment_score(left_T, right_T, ref_left, ref_right)


def _alignment_from_g1_ref(raw: dict[str, Pose7], g1_ref: dict[str, Pose7]) -> float:
    if not g1_ref.get("left") or not g1_ref.get("right"):
        return 0.0
    return alignment_score_pose7(raw["left"], raw["right"], g1_ref["left"], g1_ref["right"])


def _ref_4x4_from_g1_ref(g1_ref: dict[str, Pose7] | None, home_l: np.ndarray, home_r: np.ndarray):
    if g1_ref and g1_ref.get("left") and g1_ref.get("right"):
        from sonic_bridge.alignment import pose7_to_4x4

        return pose7_to_4x4(g1_ref["left"]), pose7_to_4x4(g1_ref["right"])
    return home_l, home_r


def _poll_editor_keys(synthetic_state: dict) -> dict | None:
    """Synthetic / Editor: y/x/c to mimic Quest Y/X and right-trigger calib."""
    import select
    import sys

    if not sys.stdin.isatty():
        return None
    try:
        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        line = sys.stdin.readline().strip().lower()
        if line in ("y", "mode"):
            return {"button_y": True, "button_x": False}
        if line in ("x", "rec"):
            return {"button_y": False, "button_x": True}
        if line in ("c", "cal", "calibrate", "trigger"):
            synthetic_state["calibrated"] = True
            print("[Pipeline] Synthetic 右扳机校准 → quest_calibrated=True")
    except Exception:
        pass
    return None


def _fill_scene_meta(state: BridgeState) -> None:
    pw = pelvis_world_packet()
    state.pelvis_world = Pose7(p=pw["p"], q=pw["q"])
    state.scene_name = SCENE_NAME
    state.scene_objects = scene_objects_packet()


def _apply_mujoco_state(state: BridgeState, q: np.ndarray) -> None:
    """Fill robot_joints, robot_actual (FK), visual_links, cameras from sim joints."""
    try:
        frames = keyframe_poses(q)
        links = visual_link_poses(q)
        d435 = d435_pose(q)
    except Exception as e:
        print(f"[Bridge] FK failed: {e}")
        return

    state.robot_joints = [float(x) for x in q]
    state.robot_actual = {
        "left": frames["left"],
        "right": frames["right"],
        "head": frames["head"],
        "torso": frames["torso"],
    }
    state.visual_links = links
    state.camera_pose = frames["head"]
    state.mirror_camera_pose = frames["head"]
    state.d435_pose = d435


def _demo_vr3pt_raw(t: float, ref: dict[str, Pose7] | None) -> dict[str, Pose7]:
    """Uncalibrated synthetic hands — intentional offset until user presses c."""
    sway = 0.08 * math.sin(t * 1.2)
    misalign = 0.12
    if ref:
        left = ref["left"]
        right = ref["right"]
        head = FIXED_VR3PT_HEAD
        return {
            "left": Pose7(p=[left.p[0] + misalign + sway, left.p[1], left.p[2]], q=left.q),
            "right": Pose7(p=[right.p[0] + misalign + sway, right.p[1], right.p[2]], q=right.q),
            "head": head,
        }
    return {
        "left": Pose7(p=[0.15 + misalign + sway, 0.25, 0.45], q=[1, 0, 0, 0]),
        "right": Pose7(p=[0.15 + misalign + sway, -0.25, 0.45], q=[1, 0, 0, 0]),
        "head": FIXED_VR3PT_HEAD,
    }


def _demo_vr3pt_calibrated(raw: dict[str, Pose7]) -> dict[str, Pose7]:
    """After synthetic calib, command wrists match MuJoCo reference."""
    return {
        "left": Pose7(p=list(raw["left"].p), q=list(raw["left"].q)),
        "right": Pose7(p=list(raw["right"].p), q=list(raw["right"].q)),
        "head": FIXED_VR3PT_HEAD,
    }


def _synthetic_vr3pt_array(vr: dict[str, Pose7]) -> np.ndarray:
    rows = []
    for key in ("left", "right", "head"):
        p = vr[key]
        rows.append([p.p[0], p.p[1], p.p[2], p.q[0], p.q[1], p.q[2], p.q[3]])
    return np.asarray(rows, dtype=np.float32)


def _apply_hand_state(state: BridgeState, sample: dict | None, controls: QuestPipelineControls) -> None:
    state.hand_state = controls.hand_state_from_sample(sample)
    lh, rh = compute_hand_joints(state.hand_state)
    state.left_hand_joints = lh
    state.right_hand_joints = rh


def _recording_row(state: BridgeState, sample: dict | None, controls: QuestPipelineControls) -> dict:
    row = {
        "display_mode": state.display_mode,
        "recording": state.recording,
        "calibrated": state.calibrated,
        "alignment_score": state.alignment_score,
        "robot_joints": state.robot_joints,
        "hand_state": state.hand_state,
        "left_hand_joints": state.left_hand_joints,
        "right_hand_joints": state.right_hand_joints,
    }
    if sample:
        row["vr_3pt_pose"] = sample.get("vr_3pt_pose")
        row["vr_3pt_raw_pose"] = sample.get("vr_3pt_raw_pose")
        row["buttons"] = {
            "a": sample.get("button_a"),
            "b": sample.get("button_b"),
            "x": sample.get("button_x"),
            "y": sample.get("button_y"),
        }
    return row


def _apply_quest_sample(
    state: BridgeState,
    sample: dict,
    home_l: np.ndarray,
    home_r: np.ndarray,
    threshold: float,
) -> None:
    quest_calibrated = bool(sample.get("quest_calibrated", False))
    state.calibrated = quest_calibrated
    ref_l, ref_r = _ref_4x4_from_g1_ref(state.g1_ref, home_l, home_r)

    if "vr_3pt_raw_pose" in sample:
        vraw = sample["vr_3pt_raw_pose"]
        state.vr_3pt_raw = _vr_dict_from_rows(vraw)
        if state.g1_ref and state.g1_ref.get("left"):
            score = _alignment_from_g1_ref(state.vr_3pt_raw, state.g1_ref)
        else:
            score = _alignment_from_vr_rows(vraw, ref_l, ref_r)
        state.alignment_score = score
        state.safe_to_switch = score >= threshold

    if quest_calibrated and "vr_3pt_pose" in sample:
        v = sample["vr_3pt_pose"]
        state.vr_3pt = _vr_dict_from_rows(v)
        state.mode = "PLANNER_VR_3PT"
    elif not quest_calibrated:
        state.mode = "CALIBRATION"
        state.vr_3pt = {}

    if sample.get("dt"):
        state.latency_ms = float(sample["dt"]) * 1000.0


def _apply_keyboard_vr(
    state: BridgeState,
    kb: KeyboardTeleop,
    threshold: float,
) -> None:
    raw = kb.vr3pt_raw()
    state.unity_head_pose = Pose7(p=list(kb.head.p), q=list(kb.head.q))
    raw["head"] = FIXED_VR3PT_HEAD
    state.vr_3pt_raw = raw
    state.calibrated = kb.calibrated
    if state.g1_ref and state.g1_ref.get("left"):
        score = _alignment_from_g1_ref(raw, state.g1_ref)
    else:
        score = 0.0
    state.alignment_score = score
    state.safe_to_switch = score >= threshold
    if kb.calibrated:
        state.vr_3pt = kb.vr3pt_calibrated()
        state.vr_3pt["head"] = FIXED_VR3PT_HEAD
        state.mode = "PLANNER_VR_3PT"
    else:
        state.vr_3pt = {}
        state.mode = "CALIBRATION"
    state.unity_head_pose = kb.head


def _apply_pc_unity_view(
    state: BridgeState,
    sample: dict | None,
    fallback_head: Pose7,
    fallback_d435: Pose7,
) -> None:
    """PC Unity legacy: unity_head_pose yaw-only; v2 uses hmd_view_pose."""
    uh = _unity_head_from_sample(sample)
    head_q = list(uh.q) if uh is not None else list(fallback_head.q)
    head_p = list(fallback_head.p)
    if state.robot_actual and state.robot_actual.get("head"):
        head_p = list(state.robot_actual["head"].p)
    state.unity_head_pose = Pose7(p=head_p, q=head_q)
    state.mirror_camera_pose = state.unity_head_pose
    state.camera_pose = state.unity_head_pose
    state.d435_pose = fallback_d435
    _apply_hmd_view_pose(state, sample, fallback_head)


def _apply_hmd_view_pose(
    state: BridgeState,
    sample: dict | None,
    fallback_head: Pose7,
) -> None:
    """Unity v2: full 6DOF camera = MuJoCo head FK + Quest HMD session delta."""
    head = (state.robot_actual or {}).get("head") or fallback_head
    rel_pos = sample.get("hmd_rel_pos") if sample else None
    rel_quat = sample.get("hmd_rel_quat") if sample else None
    try:
        from gear_sonic.utils.teleop.readers.quest_reader import build_hmd_view_pose

        d = build_hmd_view_pose(list(head.p), list(head.q), rel_pos, rel_quat)
        state.hmd_view_pose = Pose7(p=d["p"], q=d["q"])
    except ImportError:
        state.hmd_view_pose = Pose7(p=list(head.p), q=list(head.q))


def _load_keyboard_file_sample(path: str) -> dict | None:
    try:
        from gear_sonic.utils.teleop.readers.keyboard_quest_input import load_sample_from_file

        return load_sample_from_file(path)
    except ImportError:
        import json

        import numpy as np

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for key in ("vr_3pt_raw_pose", "vr_3pt_pose", "body_poses_np"):
                if key in data and data[key] is not None:
                    data[key] = np.asarray(data[key], dtype=np.float32)
            return data
        except (OSError, json.JSONDecodeError, ValueError):
            return None


def run(args: argparse.Namespace) -> None:
    home_l, home_r, home_frames = _load_g1_home_4x4()
    static_ref = _static_g1_ref(home_l, home_r, home_frames)
    standing_q = standing_body_q()
    standing_frames = keyframe_poses(standing_q)
    pc_fallback_head = standing_frames["head"]
    pc_fallback_d435 = d435_pose(standing_q)

    reader = None
    if not args.synthetic and not args.keyboard and not args.keyboard_file:
        from gear_sonic.utils.teleop.readers.quest_reader import QuestReader

        reader = QuestReader(
            source="meta_quest",
            ip_address=args.quest_ip,
            home_left_pose=home_l,
            home_right_pose=home_r,
        )
        reader.start()

    feedback: MujocoFeedbackReader | None = None
    if args.mujoco_feedback:
        feedback = MujocoFeedbackReader(
            host=args.zmq_feedback_host,
            port=args.zmq_feedback_port,
        )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    target = (args.udp_host, args.udp_port)

    tcp_relay: TcpLineRelay | None = None
    if args.tcp_relay_port:
        tcp_relay = TcpLineRelay(port=args.tcp_relay_port)

    controls = QuestPipelineControls()
    controls.manager_mode = bool(args.keyboard_file)
    if args.display_mode:
        controls.display_mode = args.display_mode.upper()

    recorder: TrajectoryRecorder | None = None
    threshold = args.align_threshold
    synthetic_state: dict = {"calibrated": False, "safe_to_switch": False}

    kb: KeyboardTeleop | None = None
    kb_inited = False
    if args.keyboard:
        kb = KeyboardTeleop(step_pos=args.kb_step, step_yaw=args.kb_yaw_step)
        if not kb.start():
            print("[Bridge] --keyboard 需要交互式终端，退出。")
            return

    if args.keyboard_file:
        mode = "keyboard-file"
    elif args.keyboard:
        mode = "keyboard"
    elif args.synthetic:
        mode = "synthetic"
    else:
        mode = "meta_quest"
    print(f"[Bridge] mode={mode} display={controls.display_mode} mujoco_feedback={args.mujoco_feedback} → UDP {target}")
    if args.tcp_relay_port:
        print(
            f"[Bridge] WSL→Windows: TCP :{args.tcp_relay_port} "
            "(mirrored WSL 无法 UDP 到 Windows；请在 Windows 跑 unity_udp_relay.ps1)"
        )
    elif args.quest_ip and args.udp_host == args.quest_ip:
        print(
            "[Bridge] Unity 收包: Quest 头显 — 须单独安装并打开 Quest Mirror APK "
            "（meta_quest_teleop 黑屏不监听 17771，头显里不会有 G1 画面）"
        )
    elif args.udp_host in ("127.0.0.1", "localhost"):
        print("[Bridge] Unity 收包: 本机 Editor Play（--udp-host 127.0.0.1）")
    elif args.udp_host == "255.255.255.255":
        print("[Bridge] Unity 收包: 局域网广播 — Editor 或 Quest APK 均须在本机监听 17771")
    else:
        print(
            f"[Bridge] Unity 收包: {args.udp_host} — WSL 直连 Windows 可能不通；"
            "请加 --tcp-relay-port 17782 + Windows unity_udp_relay.ps1"
        )
    if args.keyboard_file:
        print(f"[Bridge] Quest 数据: T3 写入 {args.keyboard_file}（T4 不直连 Quest）")
    elif mode == "meta_quest":
        print(
            "[Bridge] 警告: T4 直连 Quest 会与 T3 抢 adb/扳机；"
            "有 T3 时请用 --keyboard-file /tmp/sonic_quest_sample.json"
        )
    print("[Bridge] 校准: 对准 Unity/MuJoCo 幽灵腕 → 右扳机 → Align OK → Y 进 TELEOP")
    print("[Bridge] Y=模式 | X=录制 | 右扳机=SONIC 腕校准")
    if args.keyboard_file:
        print("[Bridge] T3 模式: X=policy  左摇杆Click=VR_3PT  Unity层随 VR_3PT 自动 TELEOP")
        print("[Bridge] T4 录制: 左握把+Y（避免与 T3 的 X 冲突）")
    if args.keyboard_file:
        print(f"[Bridge] Unity 镜像读: {args.keyboard_file}")
    elif args.keyboard:
        print("[Bridge] 键盘遥操已启用 — 焦点在本终端，按 H 看映射")
    elif args.synthetic:
        print("[Bridge] Editor: y/x/c + Enter（旧 synthetic 模式）")
    print("[Bridge] 灵巧手: 扳机>0.5 中指握合 (manager→deploy IK)")

    last_send = 0.0
    hz = args.hz
    t0 = time.time()
    cached_q: np.ndarray | None = None
    try:
        while True:
            t_loop = time.time()
            t_anim = t_loop - t0
            kb_file_sample: dict | None = None
            if args.keyboard_file:
                kb_file_sample = _load_keyboard_file_sample(args.keyboard_file)

            synthetic_buttons: dict | None = None
            if args.keyboard and kb is not None:
                synthetic_buttons = kb.poll()
                if kb.calibrated:
                    synthetic_state["calibrated"] = True
            elif args.synthetic:
                synthetic_buttons = _poll_editor_keys(synthetic_state)

            sample = reader.get_latest() if reader else kb_file_sample
            quest_calibrated = bool(sample.get("quest_calibrated")) if sample else (
                kb.calibrated if kb else synthetic_state["calibrated"]
            )
            controls_sample = sample if sample else synthetic_buttons

            if controls.recording and recorder is None:
                recorder = TrajectoryRecorder(args.record_dir)
            elif not controls.recording and recorder is not None:
                print(f"[Bridge] Recording saved: {recorder.path}")
                recorder.close()
                recorder = None

            state = BridgeState(
                display_mode=controls.display_mode,
                recording=controls.recording,
                recording_path=str(recorder.path) if recorder else None,
            )
            _fill_scene_meta(state)

            q: np.ndarray | None = None
            if feedback is not None:
                q = feedback.poll()
            if q is not None:
                cached_q = q
            elif cached_q is not None:
                q = cached_q
            elif args.synthetic:
                q = synthetic_body_q(t_anim)
            elif args.keyboard or args.keyboard_file:
                # Stable FK when deploy feedback is offline — avoid arm sine wobble flicker in Unity.
                q = standing_body_q()
            if q is not None:
                _apply_mujoco_state(state, q)

            _sync_g1_ref_from_mujoco(state, static_ref)

            if args.keyboard and kb is not None:
                head_ref = state.robot_actual.get("head") if state.robot_actual else None
                if not kb_inited and state.g1_ref:
                    kb.reset_to_ref(state.g1_ref, head_ref)
                    kb_inited = True
                kb.consume_reset(state.g1_ref, head_ref)
                _apply_keyboard_vr(state, kb, threshold)
                _apply_pc_unity_view(state, None, pc_fallback_head, pc_fallback_d435)
                state.latency_ms = 8.0 + 5 * abs(math.sin(t_anim))
            elif args.synthetic:
                ref_left = state.g1_ref.get("left") if state.g1_ref else None
                ref_right = state.g1_ref.get("right") if state.g1_ref else None
                ref = None
                if ref_left and ref_right:
                    ref = {
                        "left": ref_left,
                        "right": ref_right,
                        "head": state.robot_actual.get("head") if state.robot_actual else None,
                    }
                if synthetic_state["calibrated"] and ref:
                    raw = {
                        "left": Pose7(p=list(ref["left"].p), q=list(ref["left"].q)),
                        "right": Pose7(p=list(ref["right"].p), q=list(ref["right"].q)),
                        "head": FIXED_VR3PT_HEAD,
                    }
                else:
                    raw = _demo_vr3pt_raw(t_anim, ref)
                state.vr_3pt_raw = raw
                if state.robot_actual.get("head"):
                    state.unity_head_pose = state.robot_actual["head"]
                if state.g1_ref and state.g1_ref.get("left"):
                    score = _alignment_from_g1_ref(raw, state.g1_ref)
                else:
                    ref_l, ref_r = _ref_4x4_from_g1_ref(state.g1_ref, home_l, home_r)
                    arr = _synthetic_vr3pt_array(raw)
                    score = _alignment_from_vr_rows(arr, ref_l, ref_r)
                state.alignment_score = score
                state.safe_to_switch = score >= threshold
                synthetic_state["safe_to_switch"] = state.safe_to_switch
                state.calibrated = synthetic_state["calibrated"]
                if synthetic_state["calibrated"]:
                    state.vr_3pt = _demo_vr3pt_calibrated(raw)
                    state.mode = "PLANNER_VR_3PT"
                else:
                    state.mode = "CALIBRATION"
                    state.vr_3pt = {}
                state.latency_ms = 8.0 + 5 * abs(math.sin(t_anim))
            elif sample:
                _apply_quest_sample(state, sample, home_l, home_r, threshold)

            if args.keyboard_file:
                _apply_pc_unity_view(state, sample, pc_fallback_head, pc_fallback_d435)

            _apply_hand_state(state, sample if sample else controls_sample, controls)
            _refresh_visual_links_with_hands(state, q)

            controls.update(
                controls_sample,
                quest_calibrated=quest_calibrated,
                safe_to_switch=state.safe_to_switch,
            )

            if recorder:
                row = _recording_row(state, sample, controls)
                if (args.synthetic or args.keyboard or args.keyboard_file) and state.vr_3pt:
                    row["vr_3pt_pose"] = _synthetic_vr3pt_array(state.vr_3pt).tolist()
                if state.vr_3pt_raw:
                    row["vr_3pt_raw_pose"] = _synthetic_vr3pt_array(state.vr_3pt_raw).tolist()
                recorder.write(row)

            if t_loop - last_send >= 1.0 / hz:
                pkt_type = "ghost" if state.display_mode == "CALIBRATION" else "state"
                if not state.calibrated:
                    pkt_type = "ghost"
                pkt = state.to_packet(pkt_type)
                payload = encode_packet(pkt)
                sock.sendto(payload, target)
                if tcp_relay is not None:
                    tcp_relay.broadcast(payload)
                last_send = t_loop

            time.sleep(0.002 if args.keyboard_file else 0.005)
    except KeyboardInterrupt:
        print("\n[Bridge] Stopped.")
    finally:
        if kb is not None:
            kb.stop()
        if reader:
            reader.stop()
        if feedback:
            feedback.close()
        if tcp_relay is not None:
            tcp_relay.close()
        if recorder:
            recorder.close()
            print(f"[Bridge] Recording saved: {recorder.path}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="SONIC Quest Mirror UDP bridge (Path B + pipeline)")
    p.add_argument("--quest-ip", default=None, help="Quest WiFi IP (omit for USB)")
    p.add_argument("--synthetic", action="store_true", help="No Quest; auto-wobble wrists (legacy)")
    p.add_argument(
        "--keyboard-file",
        default=None,
        help="JSON from manager keyboard (/tmp/sonic_keyboard_sample.json)",
    )
    p.add_argument(
        "--keyboard",
        action="store_true",
        help="Local keyboard VR_3PT (Unity-only test; full pipeline use --keyboard-file)",
    )
    p.add_argument("--kb-step", type=float, default=0.012, help="Keyboard EEF step (m, --keyboard only)")
    p.add_argument("--kb-yaw-step", type=float, default=0.045, help="Keyboard head yaw step (rad)")
    p.add_argument("--display-mode", default=None, choices=("CALIBRATION", "TELEOP", "calibration", "teleop"))
    p.add_argument("--no-mujoco-feedback", dest="mujoco_feedback", action="store_false",
                   help="Disable ZMQ feedback (no FPV sync from sim)")
    p.set_defaults(mujoco_feedback=True)
    p.add_argument("--zmq-feedback-host", default="localhost")
    p.add_argument("--zmq-feedback-port", type=int, default=5557)
    p.add_argument("--udp-host", default="255.255.255.255")
    p.add_argument("--udp-port", type=int, default=17771)
    p.add_argument(
        "--tcp-relay-port",
        type=int,
        default=None,
        help="WSL TCP relay port for Windows unity_udp_relay.ps1 (mirrored WSL→Unity)",
    )
    p.add_argument("--hz", type=float, default=None)
    p.add_argument("--align-threshold", type=float, default=0.75)
    p.add_argument("--record-dir", default="recordings")
    args = p.parse_args(argv)
    if args.hz is None:
        args.hz = 60.0 if args.keyboard_file else 30.0
    run(args)


if __name__ == "__main__":
    main()
