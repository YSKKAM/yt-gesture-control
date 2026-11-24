"""
app/gesture_detection/state_machine.py

State machine and debouncer for hand poses (Closed Fist = PAUSE, Open Palm = PLAY).

Provides:
  - Multi-frame stability check (ignores momentary transitions or sensor noise)
  - Change detection (triggers only when the user switches poses, preventing repeat spam)
  - Post-trigger cooldown (avoids rapid toggling while holding a pose)
"""
from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable, List, Optional

from app.hand_tracking.tracker import HandPosition
from app.gesture_detection.validator import HandPose, GestureDirection
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
    Tracks hand poses (OPEN_PALM -> PLAY, CLOSED_FIST -> PAUSE) and fires callbacks.
    """

    def __init__(self, on_gesture: Callable[[HandPose], None]) -> None:
        self._on_gesture = on_gesture
        self._state = FSMState.IDLE
        self._last_confirmed_pose = HandPose.NONE
        self._candidate_pose = HandPose.NONE
        self._candidate_frame_count = 0
        self._cooldown_end_ms: float = 0.0

        cfg = settings.gesture
        self._stable_frames_required = getattr(cfg, "stable_frames_required", 2)
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

        # In cooldown: state remains COOLDOWN until timer expires
        if now_ms < self._cooldown_end_ms:
            self._state = FSMState.COOLDOWN
            return self._state

        if self._state == FSMState.COOLDOWN:
            self._state = FSMState.IDLE

        if hand is None or hand.confidence < self._min_confidence:
            self._candidate_pose = HandPose.NONE
            self._candidate_frame_count = 0
            self._state = FSMState.IDLE
            return self._state

        # Hand is present
        detected_pose = getattr(hand, "pose", HandPose.UNKNOWN)

        if detected_pose in (HandPose.NONE, HandPose.UNKNOWN):
            self._candidate_pose = HandPose.NONE
            self._candidate_frame_count = 0
            self._state = FSMState.HAND_DETECTED
            return self._state

        # A specific pose (OPEN_PALM or CLOSED_FIST) was detected
        self._state = FSMState.TRACKING

        if detected_pose == self._candidate_pose:
            self._candidate_frame_count += 1
        else:
            self._candidate_pose = detected_pose
            self._candidate_frame_count = 1

        # Check if held stably for required frames
        if self._candidate_frame_count >= self._stable_frames_required:
            if self._candidate_pose != self._last_confirmed_pose:
                self._last_confirmed_pose = self._candidate_pose
                self._cooldown_end_ms = now_ms + self._cooldown_ms
                self._state = FSMState.COOLDOWN
                logger.info("Pose confirmed: %s", self._last_confirmed_pose.name)
                self._on_gesture(self._last_confirmed_pose)

        return self._state

    @property
    def state(self) -> FSMState:
        return self._state

    @property
    def last_confirmed_pose(self) -> HandPose:
        return self._last_confirmed_pose

    def reset(self) -> None:
        """Force reset state (e.g. on camera toggle or disconnect)."""
        self._candidate_pose = HandPose.NONE
        self._candidate_frame_count = 0
        self._last_confirmed_pose = HandPose.NONE
        self._state = FSMState.IDLE
