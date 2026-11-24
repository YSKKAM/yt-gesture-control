"""
app/hand_tracking/tracker.py

Detects hand landmarks and classifies hand poses (OPEN_PALM, CLOSED_FIST)
using Google MediaPipe Tasks API (v1.0+) combined with geometric joint analysis.

Falls back to OpenCV skin-color contour tracker if model files are missing
or MediaPipe fails for any reason.
"""
from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.logging_setup.logger import get_logger
from app.config.settings import settings
from app.gesture_detection.validator import HandPose, classify_pose_from_landmarks

logger = get_logger(__name__)

# Model paths
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GESTURE_MODEL_PATH = _PROJECT_ROOT / "models" / "gesture_recognizer.task"
_HAND_MODEL_PATH = _PROJECT_ROOT / "models" / "hand_landmarker.task"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class HandPosition:
    """Normalized hand position (0.0–1.0), detection confidence, and pose."""
    x: float          # 0.0 = left edge, 1.0 = right edge
    y: float          # 0.0 = top edge, 1.0 = bottom edge
    confidence: float  # 0.0–1.0
    pose: HandPose = HandPose.NONE


# ---------------------------------------------------------------------------
# MediaPipe Gesture Recognizer Tracker (Primary)
# ---------------------------------------------------------------------------
class _MediaPipeGestureTracker:
    """
    Uses MediaPipe GestureRecognizer task combined with geometric landmark verification.
    Detects OPEN_PALM and CLOSED_FIST with high accuracy across all hand types and angles.
    """

    def __init__(self) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        model_path = _GESTURE_MODEL_PATH if _GESTURE_MODEL_PATH.exists() else _HAND_MODEL_PATH
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found at {model_path}")

        base_options = mp_python.BaseOptions(model_asset_path=str(model_path))

        self._has_gesture_recognizer = (model_path == _GESTURE_MODEL_PATH)
        if self._has_gesture_recognizer:
            options = mp_vision.GestureRecognizerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=settings.hand_tracking.min_detection_confidence,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=settings.hand_tracking.min_tracking_confidence,
            )
            self._recognizer = mp_vision.GestureRecognizer.create_from_options(options)
            logger.info("MediaPipe GestureRecognizer initialized with %s", model_path.name)
        else:
            options = mp_vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=settings.hand_tracking.min_detection_confidence,
                min_hand_presence_confidence=0.5,
                min_tracking_confidence=settings.hand_tracking.min_tracking_confidence,
            )
            self._recognizer = mp_vision.HandLandmarker.create_from_options(options)
            logger.info("MediaPipe HandLandmarker initialized with %s", model_path.name)

        self._landmark_id = settings.hand_tracking.tracking_landmark
        self._frame_timestamp_ms = 0

    def process(self, frame_bgr: np.ndarray) -> Optional[HandPosition]:
        """
        Process a BGR frame. Returns HandPosition with pose, or None if no hand detected.
        """
        import mediapipe as mp

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        now_ms = int(time.monotonic() * 1000)
        if now_ms <= self._frame_timestamp_ms:
            now_ms = self._frame_timestamp_ms + 1
        self._frame_timestamp_ms = now_ms

        if self._has_gesture_recognizer:
            result = self._recognizer.recognize_for_video(mp_image, self._frame_timestamp_ms)
        else:
            result = self._recognizer.detect_for_video(mp_image, self._frame_timestamp_ms)

        if not result.hand_landmarks:
            return None

        landmarks = result.hand_landmarks[0]
        lm = landmarks[self._landmark_id] if self._landmark_id < len(landmarks) else landmarks[0]
        confidence = float(lm.presence) if getattr(lm, "presence", None) is not None else 1.0

        pose = HandPose.UNKNOWN

        # 1. Check ML gesture classifier if available
        if hasattr(result, "gestures") and result.gestures and result.gestures[0]:
            top_category = result.gestures[0][0].category_name
            top_score = result.gestures[0][0].score
            if top_category == "Open_Palm" and top_score >= 0.50:
                pose = HandPose.OPEN_PALM
            elif top_category == "Closed_Fist" and top_score >= 0.50:
                pose = HandPose.CLOSED_FIST

        # 2. Corroborate or determine with geometric landmark analysis
        if pose == HandPose.UNKNOWN:
            pose = classify_pose_from_landmarks(landmarks)

        return HandPosition(x=lm.x, y=lm.y, confidence=confidence, pose=pose)

    def close(self) -> None:
        if self._recognizer:
            self._recognizer.close()


# ---------------------------------------------------------------------------
# OpenCV contour fallback tracker
# ---------------------------------------------------------------------------
class _OpenCVFallbackTracker:
    """
    Fallback hand tracker using skin-color and contour solidity.
    Solidity > 0.82 indicates a closed fist, lower indicates extended fingers.
    """

    def __init__(self) -> None:
        logger.warning("Using OpenCV fallback tracker. Install MediaPipe models for best accuracy.")

    def process(self, frame_bgr: np.ndarray) -> Optional[HandPosition]:
        h, w = frame_bgr.shape[:2]

        ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(ycrcb,
                           np.array([0, 133, 77], dtype=np.uint8),
                           np.array([255, 173, 127], dtype=np.uint8))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        if area < (w * h * 0.01):
            return None

        hull = cv2.convexHull(largest)
        hull_area = cv2.contourArea(hull)
        solidity = float(area) / hull_area if hull_area > 0 else 0

        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None

        cx = (M["m10"] / M["m00"]) / w
        cy = (M["m01"] / M["m00"]) / h

        # Solidity heuristic: high solidity -> Fist, lower -> Palm
        if solidity >= 0.82:
            pose = HandPose.CLOSED_FIST
        elif solidity <= 0.72:
            pose = HandPose.OPEN_PALM
        else:
            pose = HandPose.UNKNOWN

        return HandPosition(x=cx, y=cy, confidence=min(1.0, area / (w * h * 0.05)), pose=pose)

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------
def create_tracker():
    """Returns the best available hand & pose tracker."""
    try:
        tracker = _MediaPipeGestureTracker()
        return tracker
    except Exception as exc:
        logger.error("MediaPipe initialization failed (%s) — using OpenCV fallback", exc)
        return _OpenCVFallbackTracker()
