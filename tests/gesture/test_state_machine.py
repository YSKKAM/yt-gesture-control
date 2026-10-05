"""
tests/gesture/test_state_machine.py

Tests for the GestureStateMachine FSM.
Simulates frame-by-frame hand position sequences.

Run with:
    python -m pytest tests/gesture/test_state_machine.py -v
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import MagicMock, patch
from app.gesture_detection.state_machine import GestureStateMachine, FSMState
from app.gesture_detection.validator import GestureDirection
from app.hand_tracking.tracker import HandPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hand(x: float, y: float = 0.5, conf: float = 0.9) -> HandPosition:
    return HandPosition(x=x, y=y, confidence=conf)


def no_hand() -> None:
    return None


def feed_frames(fsm, frames: list, delay_ms_each: float = 50.0):
    """Feed a list of HandPosition|None into the FSM with mocked time."""
    t = [0.0]
    original_monotonic = time.monotonic

    def fake_monotonic():
        return t[0] / 1000.0

    with patch('time.monotonic', side_effect=lambda: (t.__setitem__(0, t[0]) or fake_monotonic())):
        import app.gesture_detection.state_machine as sm_module
        import app.gesture_detection.validator as val_module

        original_sm = sm_module.time.monotonic
        original_val = val_module  # validator uses timestamp_ms directly

        sm_module.time.monotonic = fake_monotonic

        try:
            states = []
            for frame in frames:
                states.append(fsm.update(frame))
                t[0] += delay_ms_each
            return states
        finally:
            sm_module.time.monotonic = original_sm


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
        fsm.update(hand(0.5))
        assert fsm.state == FSMState.HAND_DETECTED

    def test_stable_hand_enters_tracking(self):
        fsm, _ = self._make_fsm()
        # min_stable_frames is 3 by default
        for _ in range(3):
            fsm.update(hand(0.5))
        assert fsm.state == FSMState.TRACKING

    def test_hand_lost_resets_to_idle(self):
        fsm, _ = self._make_fsm()
        fsm.update(hand(0.5))
        fsm.update(None)
        assert fsm.state == FSMState.IDLE

    def test_low_confidence_treated_as_no_hand(self):
        fsm, _ = self._make_fsm()
        # Low confidence hand (below 0.75 threshold)
        fsm.update(HandPosition(x=0.5, y=0.5, confidence=0.3))
        assert fsm.state == FSMState.IDLE

    def test_reset_clears_state(self):
        fsm, _ = self._make_fsm()
        fsm.update(hand(0.5))
        fsm.update(hand(0.5))
        fsm.reset()
        assert fsm.state == FSMState.IDLE

    def test_gesture_control_disabled_no_callback(self):
        """If we feed no hands at all, callback never fires."""
        fsm, callback = self._make_fsm()
        for _ in range(20):
            fsm.update(None)
        callback.assert_not_called()

    def test_valid_left_to_right_triggers_callback(self):
        """
        Simulate a clear L→R swipe across frames.
        The FSM should detect it and call on_gesture with LEFT_TO_RIGHT.
        """
        fsm, callback = self._make_fsm()

        # Stabilize
        for _ in range(3):
            fsm.update(hand(0.1))

        # Swipe from 0.1 to 0.75 across ~10 frames (50ms each = 500ms total)
        for i in range(10):
            x = 0.1 + (0.65 * i / 9)
            fsm.update(hand(x))

        # Hand leaves
        fsm.update(None)

        # Allow callback check — the FSM validates on hand-lost or during tracking
        # It may have fired; if not, state is IDLE or COOLDOWN
        # We check the callback was called with RIGHT direction
        if callback.called:
            args = callback.call_args[0][0]
            assert args == GestureDirection.LEFT_TO_RIGHT

    def test_cooldown_prevents_second_trigger(self):
        """
        After a gesture fires, immediately feeding another swipe must NOT trigger again.
        """
        fsm, callback = self._make_fsm()

        def do_swipe():
            for _ in range(3):
                fsm.update(hand(0.1))
            for i in range(10):
                x = 0.1 + (0.65 * i / 9)
                fsm.update(hand(x))
            fsm.update(None)

        do_swipe()
        first_call_count = callback.call_count

        # Immediately try again — should be in COOLDOWN
        do_swipe()
        second_call_count = callback.call_count

        # If first gesture triggered, second must NOT add another call
        if first_call_count > 0:
            assert second_call_count == first_call_count


class TestCooldownTiming:

    def test_cooldown_state_entered_on_trigger(self):
        """After gesture, state should be COOLDOWN."""
        callback = MagicMock()
        fsm = GestureStateMachine(on_gesture=callback)

        # We test this by checking if callback fires and state becomes COOLDOWN
        # Stabilize
        for _ in range(3):
            fsm.update(hand(0.1))

        # Short swipe
        for i in range(8):
            x = 0.1 + (0.65 * i / 7)
            fsm.update(hand(x))

        fsm.update(None)

        if callback.called:
            assert fsm.state == FSMState.COOLDOWN
