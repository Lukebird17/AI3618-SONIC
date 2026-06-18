"""G1 gripper IK — same path as pico_manager / official SONIC PicoStreamer."""

from __future__ import annotations


def compute_hand_joints(hand_state: dict[str, float]) -> tuple[list[float], list[float]]:
    """Map trigger/grip → 7-DOF left/right hand joint vectors (SONIC Dex3)."""
    try:
        from gear_sonic.scripts.pico_manager_thread_server import (
            compute_hand_joints_from_inputs,
            init_hand_ik_solvers,
        )
    except Exception as e:
        print(f"[HandIK] pico_manager import failed ({e}); hand joints zero.")
        return [0.0] * 7, [0.0] * 7

    left_solver, right_solver = init_hand_ik_solvers()
    if left_solver is None or right_solver is None:
        return [0.0] * 7, [0.0] * 7

    lt = float(hand_state.get("left_trigger", 0.0))
    lg = float(hand_state.get("left_grip", 0.0))
    rt = float(hand_state.get("right_trigger", 0.0))
    rg = float(hand_state.get("right_grip", 0.0))
    lh, rh = compute_hand_joints_from_inputs(
        left_solver, right_solver, lt, lg, rt, rg
    )
    return lh.reshape(-1).astype(float).tolist(), rh.reshape(-1).astype(float).tolist()
