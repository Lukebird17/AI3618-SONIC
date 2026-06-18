"""Quest controller edge detection for Unity pipeline (Y=mode, X=record)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class QuestPipelineControls:
    """
    Button map (non-trigger):
      Y — toggle Unity display: CALIBRATION ↔ TELEOP (keyboard/synthetic bridge only)
      X — toggle JSONL recording (keyboard/synthetic bridge only)

    When manager_mode=True (T4 reads T3 sample file):
      display_mode follows sample['unity_display_mode'] from manager
      X/Y are reserved for T3 (policy / VR_3PT) — not used here

    Unchanged SONIC official:
      Right trigger — QuestReader wrist calibration (once; Menu+trigger to redo)
      Trigger/Grip — dexterous hand IK in pico_manager (not handled here)
    """

    display_mode: str = "CALIBRATION"
    recording: bool = False
    manager_mode: bool = False
    _prev_y: bool = field(default=False, repr=False)
    _prev_x: bool = field(default=False, repr=False)
    _prev_rec_combo: bool = field(default=False, repr=False)

    def update(
        self,
        sample: dict | None,
        *,
        quest_calibrated: bool = False,
        safe_to_switch: bool = False,
    ) -> tuple[bool, bool]:
        """Return (display_mode_changed, recording_changed)."""
        if not sample:
            return False, False

        if self.manager_mode:
            dm = sample.get("unity_display_mode")
            if dm:
                dm = str(dm).upper()
                if dm != self.display_mode:
                    self.display_mode = dm
                    print(f"[Pipeline] Display mode → {self.display_mode} (from T3)")
                    return True, False
            # Recording follows T3 manager (Quest X button)
            want_rec = sample.get("sonic_recording")
            rec_changed = False
            if want_rec is not None:
                want_rec = bool(want_rec)
                if want_rec != self.recording:
                    self.recording = want_rec
                    rec_changed = True
                    state = "ON" if self.recording else "OFF"
                    print(f"[Pipeline] Recording {state} (T3 X)")
            return False, rec_changed

        y = bool(sample.get("button_y", False))
        x = bool(sample.get("button_x", False))
        mode_changed = False
        rec_changed = False

        if y and not self._prev_y:
            if self.display_mode == "CALIBRATION":
                if not quest_calibrated:
                    print("[Pipeline] TELEOP blocked: 右扳机完成 SONIC 校准后再按 Y")
                elif not safe_to_switch:
                    print("[Pipeline] TELEOP blocked: 把手柄对准 MuJoCo/Unity 幽灵腕 (Align)")
                else:
                    self.display_mode = "TELEOP"
                    mode_changed = True
                    print(f"[Pipeline] Display mode → {self.display_mode} (Y)")
            else:
                self.display_mode = "CALIBRATION"
                mode_changed = True
                print(f"[Pipeline] Display mode → {self.display_mode} (Y)")

        if x and not self._prev_x:
            self.recording = not self.recording
            rec_changed = True
            state = "ON" if self.recording else "OFF"
            print(f"[Pipeline] Recording {state} (X)")

        self._prev_y = y
        self._prev_x = x
        return mode_changed, rec_changed

    def hand_state_from_sample(self, sample: dict | None) -> dict[str, float]:
        if not sample:
            return {
                "left_trigger": 0.0,
                "right_trigger": 0.0,
                "left_grip": 0.0,
                "right_grip": 0.0,
            }
        return {
            "left_trigger": float(sample.get("left_trigger", 0.0)),
            "right_trigger": float(sample.get("right_trigger", 0.0)),
            "left_grip": float(sample.get("left_grip", 0.0)),
            "right_grip": float(sample.get("right_grip", 0.0)),
        }
