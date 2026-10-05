"""
app/gesture_detection/state_machine.py

Gesture finite state machine.

States:
  IDLE          → waiting for a hand to appear
  HAND_DETECTED → hand present, checking for stability
  TRACKING      → accumulating trajectory
  COOLDOWN      → post-trigger lockout

The FSM is driven by calling update() once per frame with an
Optional[HandPosition]. When a gesture is confirmed it calls
the registered on_gesture callback with the GestureDirection.

Thread-safety: designed to be called from a single thread (the
camera processing loop). The callback may dispatch to another thread.
"""
from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable, List, Optional

from app.hand_tracking.tracker import HandPosition
from app.gesture_detection.validator import (
    GestureDirection, TrajectoryPoint, validate_gesture
)
from app.config.settings import settings
from app.logging_setup.logger import get_logger

logger = get_logger(__name__)


class FSMState(Enum):
    IDLE = auto()
    HAND_DETECTED = auto()
    TRACKING = auto()
    COOLDOWN = auto()


class GestureStateMachine:
    """
    Processes a stream of Optional[HandPosition] and fires gesture callbacks.

    Usage:
        fsm = GestureStateMachine(on_gesture=my_callback)
        while running:
            pos = tracker.process(frame)
            fsm.update(pos)
    """

    def __init__(self, on_gesture: Callable[[GestureDirection], None]) -> None:
        self._on_gesture = on_gesture
        self._state = FSMState.IDLE
        self._trajectory: List[TrajectoryPoint] = []
        self._stable_frame_count = 0
        self._cooldown_end_ms: float = 0.0

        cfg = settings.gesture
        self._min_stable_frames = cfg.min_stable_frames
        self._cooldown_ms = cfg.cooldown_ms
        self._min_confidence = settings.hand_tracking.min_detection_confidence

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, hand: Optional[HandPosition]) -> FSMState:
        """
        Feed one frame's detection result.
        Returns the current FSM state after processing.
        """
        now_ms = time.monotonic() * 1000

        if self._state == FSMState.COOLDOWN:
            if now_ms >= self._cooldown_end_ms:
                logger.debug("Cooldown expired — returning to IDLE")
                self._transition(FSMState.IDLE)
            return self._state

        if hand is None or hand.confidence < self._min_confidence:
            self._on_hand_lost()
            return self._state

        # Hand is present and confident
        if self._state == FSMState.IDLE:
            self._stable_frame_count = 1
            self._transition(FSMState.HAND_DETECTED)

        elif self._state == FSMState.HAND_DETECTED:
            self._stable_frame_count += 1
            if self._stable_frame_count >= self._min_stable_frames:
                self._trajectory = [TrajectoryPoint(hand.x, hand.y, now_ms)]
                self._transition(FSMState.TRACKING)

        elif self._state == FSMState.TRACKING:
            self._trajectory.append(TrajectoryPoint(hand.x, hand.y, now_ms))
            self._try_validate()

        return self._state

    @property
    def state(self) -> FSMState:
        return self._state

    def reset(self) -> None:
        """Force reset to IDLE (e.g. on camera disconnect)."""
        self._trajectory.clear()
        self._stable_frame_count = 0
        self._transition(FSMState.IDLE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _on_hand_lost(self) -> None:
        """Hand disappeared. If we were tracking, try to validate what we have."""
        if self._state == FSMState.TRACKING and len(self._trajectory) >= 2:
            self._try_validate()
        self._trajectory.clear()
        self._stable_frame_count = 0
        if self._state != FSMState.COOLDOWN:
            self._transition(FSMState.IDLE)

    def _try_validate(self) -> None:
        """Attempt to validate the current trajectory."""
        result = validate_gesture(self._trajectory)
        if result.valid:
            logger.info("Gesture confirmed: %s", result.direction.name)
            self._trajectory.clear()
            self._stable_frame_count = 0
            self._cooldown_end_ms = time.monotonic() * 1000 + self._cooldown_ms
            self._transition(FSMState.COOLDOWN)
            self._on_gesture(result.direction)
        # If not valid yet, keep accumulating (TRACKING continues)

    def _transition(self, new_state: FSMState) -> None:
        if new_state != self._state:
            logger.debug("FSM: %s → %s", self._state.name, new_state.name)
            self._state = new_state
