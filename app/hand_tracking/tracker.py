"""
app/hand_tracking/tracker.py

Detects hand landmarks using MediaPipe Tasks API (v1.0+).
MediaPipe 1.0 removed the old `mp.solutions` API and now uses `mp.tasks.vision`.

Returns normalized (x, y) position of the tracking landmark.

Falls back to OpenCV skin-color contour tracker if model file is missing
or MediaPipe fails for any reason.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.logging_setup.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

# Path to the downloaded hand landmarker model
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MODEL_PATH = _PROJECT_ROOT / "models" / "hand_landmarker.task"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
@dataclass
class HandPosition:
    """Normalized hand position (0.0–1.0) and detection confidence."""
    x: float          # 0.0 = left edge, 1.0 = right edge
    y: float          # 0.0 = top edge, 1.0 = bottom edge
    confidence: float  # 0.0–1.0


# ---------------------------------------------------------------------------
# MediaPipe Tasks-based tracker (primary — uses MediaPipe 1.0+ API)
# ---------------------------------------------------------------------------
class _MediaPipeTasksTracker:
    def __init__(self) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision

        if not _MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Hand landmarker model not found at {_MODEL_PATH}. "
                "Run: python -c \"import urllib.request; urllib.request.urlretrieve("
                "'https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
                "hand_landmarker/float16/1/hand_landmarker.task', 'models/hand_landmarker.task')\""
            )

        base_options = mp_python.BaseOptions(model_asset_path=str(_MODEL_PATH))
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=settings.hand_tracking.min_detection_confidence,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=settings.hand_tracking.min_tracking_confidence,
        )
        self._detector = mp_vision.HandLandmarker.create_from_options(options)
        self._landmark_id = settings.hand_tracking.tracking_landmark
        self._frame_timestamp_ms = 0
        logger.info("MediaPipe Tasks HandLandmarker initialized (landmark=%d)", self._landmark_id)

    def process(self, frame_bgr: np.ndarray) -> Optional[HandPosition]:
        """
        Process a BGR frame. Returns HandPosition or None if no hand detected.
        """
        import mediapipe as mp

        # Convert BGR → RGB, wrap in MediaPipe Image
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # Increment timestamp (VIDEO mode requires monotonically increasing timestamps)
        self._frame_timestamp_ms += 50  # ~20fps

        result = self._detector.detect_for_video(mp_image, self._frame_timestamp_ms)

        if not result.hand_landmarks:
            return None

        # Use first detected hand
        landmarks = result.hand_landmarks[0]
        lm = landmarks[self._landmark_id]

        # Get handedness confidence if available
        confidence = 1.0
        if result.handedness:
            confidence = result.handedness[0][0].score

        return HandPosition(x=lm.x, y=lm.y, confidence=confidence)

    def close(self) -> None:
        if self._detector:
            self._detector.close()


# ---------------------------------------------------------------------------
# OpenCV skin-color contour fallback tracker
# ---------------------------------------------------------------------------
class _OpenCVFallbackTracker:
    """
    Rough hand detection using YCrCb skin-color segmentation.
    Less accurate than MediaPipe — only used when model is unavailable.
    """

    def __init__(self) -> None:
        logger.warning(
            "Using OpenCV skin-color fallback hand tracker. "
            "Accuracy is reduced. Ensure models/hand_landmarker.task exists."
        )

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

        if area < (w * h * 0.005):
            return None

        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None

        cx = M["m10"] / M["m00"]
        cy = M["m01"] / M["m00"]

        return HandPosition(
            x=cx / w,
            y=cy / h,
            confidence=min(1.0, area / (w * h * 0.05))
        )

    def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------
def create_tracker():
    """
    Returns a MediaPipe Tasks tracker if model is available, else OpenCV fallback.
    """
    try:
        tracker = _MediaPipeTasksTracker()
        logger.info("Using MediaPipe Tasks hand tracker")
        return tracker
    except FileNotFoundError as exc:
        logger.error("Model file missing: %s — using OpenCV fallback", exc)
        return _OpenCVFallbackTracker()
    except ImportError as exc:
        logger.warning("MediaPipe import failed (%s) — using OpenCV fallback", exc)
        return _OpenCVFallbackTracker()
    except Exception as exc:
        logger.error("MediaPipe Tasks failed to initialize (%s) — using OpenCV fallback", exc)
        return _OpenCVFallbackTracker()
