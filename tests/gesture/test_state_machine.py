"""
tests/gesture/test_state_machine.py

Tests for GestureStateMachine with Closed Fist and Open Palm poses.

Run with:
    python -m pytest tests/gesture/test_state_machine.py -v
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import MagicMock
from app.gesture_detection.state_machine import GestureStateMachine, FSMState
from app.gesture_detection.validator import HandPose
from app.hand_tracking.tracker import HandPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hand(x: float = 0.5, y: float = 0.5, conf: float = 0.9, pose: HandPose = HandPose.NONE) -> HandPosition:
    return HandPosition(x=x, y=y, confidence=conf, pose=pose)


class TestStateMachine:

    def _make_fsm(self):
        callback = MagicMock()
        fsm = GestureStateMachine(on_gesture=callback)
        return fsm, callback

    def test_initial_state_is_idle(self):
        fsm, _ = self._make_fsm()
        assert fsm.state == FSMState.IDLE

    def test_no_hand_stays_idle(self):
        fsm, _ = self._make_fsm()
        for _ in range(10):
            fsm.update(None)
        assert fsm.state == FSMState.IDLE

    def test_hand_detected_transitions(self):
        fsm, _ = self._make_fsm()
        fsm.update(hand(0.5, pose=HandPose.UNKNOWN))
        assert fsm.state == FSMState.HAND_DETECTED

    def test_hand_lost_resets_to_idle(self):
        fsm, _ = self._make_fsm()
        fsm.update(hand(0.5, pose=HandPose.CLOSED_FIST))
        fsm.update(None)
        assert fsm.state == FSMState.IDLE

    def test_low_confidence_treated_as_no_hand(self):
        fsm, _ = self._make_fsm()
        fsm.update(hand(0.5, conf=0.2, pose=HandPose.CLOSED_FIST))
        assert fsm.state == FSMState.IDLE

    def test_reset_clears_state(self):
        fsm, _ = self._make_fsm()
        fsm.update(hand(0.5, pose=HandPose.OPEN_PALM))
        fsm.reset()
        assert fsm.state == FSMState.IDLE
        assert fsm.last_confirmed_pose == HandPose.NONE

    def test_stable_fist_triggers_pause(self):
        """Holding a closed fist stably for required frames triggers callback."""
        fsm, callback = self._make_fsm()
        for _ in range(3):
            fsm.update(hand(0.5, pose=HandPose.CLOSED_FIST))

        assert callback.call_count == 1
        assert callback.call_args[0][0] == HandPose.CLOSED_FIST
        assert fsm.state == FSMState.COOLDOWN

    def test_holding_fist_does_not_repeat_trigger(self):
        """Holding a fist continuously should only trigger once, not repeatedly."""
        fsm, callback = self._make_fsm()
        for _ in range(10):
            fsm.update(hand(0.5, pose=HandPose.CLOSED_FIST))
            time.sleep(0.01)

        assert callback.call_count == 1

    def test_stable_palm_triggers_play(self):
        """Showing an open palm triggers PLAY."""
        fsm, callback = self._make_fsm()
        for _ in range(3):
            fsm.update(hand(0.5, pose=HandPose.OPEN_PALM))

        assert callback.call_count == 1
        assert callback.call_args[0][0] == HandPose.OPEN_PALM

    def test_switching_fist_to_palm(self):
        """Switching from Fist to Palm triggers Pause then Play."""
        fsm, callback = self._make_fsm()

        # Fist triggers Pause
        for _ in range(3):
            fsm.update(hand(0.5, pose=HandPose.CLOSED_FIST))
        assert callback.call_count == 1
        assert callback.call_args[0][0] == HandPose.CLOSED_FIST

        # End cooldown
        fsm._cooldown_end_ms = 0

        # Switch to Open Palm triggers Play
        for _ in range(3):
            fsm.update(hand(0.5, pose=HandPose.OPEN_PALM))

        assert callback.call_count == 2
        assert callback.call_args[0][0] == HandPose.OPEN_PALM
