"""
app/gesture_detection/validator.py

Pure, stateless validation of a completed gesture candidate.
No camera, no tracking — only math on trajectory data.

All input coordinates are normalized (0.0–1.0).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple

from app.config.settings import settings
from app.logging_setup.logger import get_logger

logger = get_logger(__name__)


class GestureDirection(Enum):
    LEFT_TO_RIGHT = auto()   # → PAUSE
    RIGHT_TO_LEFT = auto()   # → PLAY
    NONE = auto()


@dataclass
class TrajectoryPoint:
    """Single tracked position in a gesture trajectory."""
    x: float        # normalized 0.0–1.0
    y: float        # normalized 0.0–1.0
    timestamp_ms: float   # milliseconds since epoch


@dataclass
class ValidationResult:
    valid: bool
    direction: GestureDirection
    reason: str  # human-readable, used in logs


def validate_gesture(trajectory: List[TrajectoryPoint]) -> ValidationResult:
    """
    Validate a candidate gesture trajectory.

    A trajectory is a time-ordered list of normalized hand positions.
    Returns a ValidationResult. All thresholds come from config.

    Rules (all must pass):
      1. Minimum number of points (at least 2 meaningful frames)
      2. Duration within [min_gesture_duration_ms, max_gesture_duration_ms]
      3. Net horizontal displacement >= min_displacement_x
      4. Net vertical displacement <= max_displacement_y
      5. Horizontal-to-vertical ratio >= direction_ratio
      6. Average speed >= min_speed
      7. Direction is monotonically consistent (no reversals mid-gesture)
    """
    cfg = settings.gesture
    NONE_RESULT = lambda reason: ValidationResult(False, GestureDirection.NONE, reason)

    # Rule 1: minimum points
    if len(trajectory) < 2:
        return NONE_RESULT("trajectory too short")

    x_start = trajectory[0].x
    y_start = trajectory[0].y
    x_end = trajectory[-1].x
    y_end = trajectory[-1].y
    t_start = trajectory[0].timestamp_ms
    t_end = trajectory[-1].timestamp_ms

    delta_x = x_end - x_start          # signed: positive = L→R
    delta_y = y_end - y_start
    abs_dx = abs(delta_x)
    abs_dy = abs(delta_y)
    duration_ms = t_end - t_start

    # Rule 2: duration
    if duration_ms < cfg.min_gesture_duration_ms:
        return NONE_RESULT(f"gesture too fast ({duration_ms:.0f}ms < {cfg.min_gesture_duration_ms}ms)")
    if duration_ms > cfg.max_gesture_duration_ms:
        return NONE_RESULT(f"gesture too slow ({duration_ms:.0f}ms > {cfg.max_gesture_duration_ms}ms)")

    # Rule 3: horizontal displacement (use >= to correctly include exact-threshold values)
    if abs_dx < cfg.min_displacement_x - 1e-9:
        return NONE_RESULT(
            f"displacement too small ({abs_dx:.3f} < {cfg.min_displacement_x})"
        )

    # Rule 4: vertical displacement
    if abs_dy > cfg.max_displacement_y:
        return NONE_RESULT(
            f"too much vertical movement ({abs_dy:.3f} > {cfg.max_displacement_y})"
        )

    # Rule 5: horizontal dominance
    if abs_dy > 0 and (abs_dx / abs_dy) < cfg.direction_ratio:
        return NONE_RESULT(
            f"not horizontal enough (dx/dy={abs_dx/abs_dy:.2f} < {cfg.direction_ratio})"
        )

    # Rule 6: average speed (displacement / duration in seconds)
    duration_s = duration_ms / 1000.0
    speed = abs_dx / duration_s if duration_s > 0 else 0
    if speed < cfg.min_speed:
        return NONE_RESULT(f"too slow (speed={speed:.3f} < {cfg.min_speed})")

    # Rule 7: directional consistency — no reversals > 30% of max displacement
    reversal_threshold = abs_dx * 0.30
    direction_sign = 1 if delta_x > 0 else -1
    prev_x = trajectory[0].x
    for pt in trajectory[1:]:
        step = (pt.x - prev_x) * direction_sign
        if step < -reversal_threshold:
            return NONE_RESULT("direction reversal detected mid-gesture")
        prev_x = pt.x

    # All rules passed — determine direction
    direction = (
        GestureDirection.LEFT_TO_RIGHT if delta_x > 0
        else GestureDirection.RIGHT_TO_LEFT
    )
    logger.debug(
        "Gesture valid: %s dx=%.3f dy=%.3f dur=%.0fms spd=%.3f",
        direction.name, delta_x, delta_y, duration_ms, speed
    )
    return ValidationResult(True, direction, "OK")
