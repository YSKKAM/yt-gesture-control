"""
tests/gesture/test_validator.py

Pure unit tests for the gesture validator.
No camera, no MediaPipe, no hardware required.
All tests use synthetic trajectory data.

Run with:
    python -m pytest tests/gesture/test_validator.py -v
"""
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from app.gesture_detection.validator import (
    validate_gesture, TrajectoryPoint, GestureDirection
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_trajectory(x_start: float, x_end: float, y_start: float = 0.5,
                    y_end: float = 0.5, duration_ms: float = 400,
                    points: int = 10) -> list:
    """Generate a linear trajectory between two points."""
    traj = []
    for i in range(points):
        t = i / (points - 1)
        x = x_start + (x_end - x_start) * t
        y = y_start + (y_end - y_start) * t
        ts = t * duration_ms
        traj.append(TrajectoryPoint(x=x, y=y, timestamp_ms=ts))
    return traj


def make_noisy_trajectory(x_start, x_end, noise=0.02, **kwargs) -> list:
    """Trajectory with small random noise on X."""
    import random
    traj = make_trajectory(x_start, x_end, **kwargs)
    for pt in traj:
        pt.x += random.uniform(-noise, noise)
    return traj


# ---------------------------------------------------------------------------
# Valid gestures
# ---------------------------------------------------------------------------

class TestValidGestures:

    def test_clear_left_to_right(self):
        traj = make_trajectory(0.1, 0.7, duration_ms=400)
        result = validate_gesture(traj)
        assert result.valid
        assert result.direction == GestureDirection.LEFT_TO_RIGHT

    def test_clear_right_to_left(self):
        traj = make_trajectory(0.8, 0.15, duration_ms=400)
        result = validate_gesture(traj)
        assert result.valid
        assert result.direction == GestureDirection.RIGHT_TO_LEFT

    def test_minimum_displacement_exactly_met(self):
        """Exactly at the threshold — should pass."""
        traj = make_trajectory(0.1, 0.30, duration_ms=400)
        result = validate_gesture(traj)
        assert result.valid

    def test_fast_swipe_still_valid(self):
        """Fast swipe within min duration."""
        traj = make_trajectory(0.1, 0.7, duration_ms=200)
        result = validate_gesture(traj)
        assert result.valid

    def test_slow_valid_swipe(self):
        """Swipe at upper valid duration bound."""
        traj = make_trajectory(0.1, 0.9, duration_ms=1400)
        result = validate_gesture(traj)
        assert result.valid


# ---------------------------------------------------------------------------
# Invalid gestures
# ---------------------------------------------------------------------------

class TestInvalidGestures:

    def test_too_small_displacement(self):
        """Hand moved only 8% of frame width — not enough."""
        traj = make_trajectory(0.4, 0.48, duration_ms=300)
        result = validate_gesture(traj)
        assert not result.valid
        assert "displacement" in result.reason

    def test_too_slow(self):
        """Slow drift across the frame over 2 seconds — over max duration."""
        traj = make_trajectory(0.1, 0.8, duration_ms=1600)
        result = validate_gesture(traj)
        assert not result.valid

    def test_too_fast(self):
        """Single-frame spike — under min duration."""
        traj = make_trajectory(0.1, 0.9, duration_ms=50)
        result = validate_gesture(traj)
        assert not result.valid

    def test_vertical_movement(self):
        """Pure vertical movement — should be rejected."""
        traj = make_trajectory(0.5, 0.5, y_start=0.1, y_end=0.8, duration_ms=400)
        result = validate_gesture(traj)
        assert not result.valid

    def test_diagonal_movement_too_steep(self):
        """Diagonal where vertical component is too large."""
        traj = make_trajectory(0.2, 0.7, y_start=0.2, y_end=0.7, duration_ms=400)
        result = validate_gesture(traj)
        assert not result.valid

    def test_tiny_movement_both_axes(self):
        """Typing-level movement — both axes tiny."""
        traj = make_trajectory(0.45, 0.48, y_start=0.5, y_end=0.52, duration_ms=200)
        result = validate_gesture(traj)
        assert not result.valid

    def test_single_point(self):
        """Only one position — cannot be a gesture."""
        traj = [TrajectoryPoint(x=0.5, y=0.5, timestamp_ms=0)]
        result = validate_gesture(traj)
        assert not result.valid

    def test_empty_trajectory(self):
        result = validate_gesture([])
        assert not result.valid

    def test_no_movement(self):
        """Hand held still — 10 identical positions."""
        traj = [TrajectoryPoint(x=0.5, y=0.5, timestamp_ms=float(i * 50))
                for i in range(10)]
        result = validate_gesture(traj)
        assert not result.valid

    def test_direction_reversal(self):
        """Swipe right then back — should be rejected."""
        traj = []
        # Go right from 0.1 to 0.6
        for i in range(6):
            traj.append(TrajectoryPoint(x=0.1 + i * 0.1, y=0.5,
                                        timestamp_ms=float(i * 80)))
        # Then come back left to 0.2
        for i in range(4):
            traj.append(TrajectoryPoint(x=0.6 - i * 0.1, y=0.5,
                                        timestamp_ms=float((6 + i) * 80)))
        result = validate_gesture(traj)
        assert not result.valid

    def test_camera_jitter_tiny_positions(self):
        """Sub-pixel noise around a fixed point."""
        import random
        traj = [
            TrajectoryPoint(x=0.5 + random.uniform(-0.01, 0.01),
                            y=0.5 + random.uniform(-0.01, 0.01),
                            timestamp_ms=float(i * 50))
            for i in range(20)
        ]
        result = validate_gesture(traj)
        assert not result.valid


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_two_points_minimum(self):
        """Exactly two points — valid if thresholds met."""
        traj = [
            TrajectoryPoint(x=0.1, y=0.5, timestamp_ms=0),
            TrajectoryPoint(x=0.7, y=0.5, timestamp_ms=400),
        ]
        result = validate_gesture(traj)
        assert result.valid
        assert result.direction == GestureDirection.LEFT_TO_RIGHT

    def test_large_displacement(self):
        """Full-frame swipe — definitely valid."""
        traj = make_trajectory(0.02, 0.98, duration_ms=500)
        result = validate_gesture(traj)
        assert result.valid

    def test_noisy_but_valid_swipe(self):
        """Realistic noisy trajectory still valid if overall direction is clear."""
        traj = make_noisy_trajectory(0.1, 0.75, noise=0.015, duration_ms=400)
        result = validate_gesture(traj)
        assert result.valid
