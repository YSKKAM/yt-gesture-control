"""
app/camera/capture.py

Manages webcam lifecycle: open, read frames, release.
Thread-safe. Never crashes the calling thread on camera failure.
"""
from __future__ import annotations

import threading
import time
from typing import Optional, Tuple

import cv2
import numpy as np

from app.logging_setup.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class CameraCapture:
    """
    Encapsulates OpenCV VideoCapture.

    Usage:
        cam = CameraCapture()
        ok = cam.open()
        frame = cam.read_frame()   # returns None on failure
        cam.release()
    """

    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._device_index = settings.camera.device_index
        self._width = settings.camera.width
        self._height = settings.camera.height
        self._fps = settings.camera.fps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """
        Open the webcam.
        Returns True on success, False if the camera is unavailable.
        """
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return True  # already open

            logger.info("Opening camera device %d at %dx%d @ %d fps",
                        self._device_index, self._width, self._height, self._fps)
            cap = cv2.VideoCapture(self._device_index, cv2.CAP_DSHOW)

            if not cap.isOpened():
                logger.warning("Camera device %d could not be opened", self._device_index)
                cap.release()
                return False

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            cap.set(cv2.CAP_PROP_FPS, self._fps)
            # Reduce internal buffer to 1 frame to avoid stale frames
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self._cap = cap
            logger.info("Camera initialized successfully")
            return True

    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read one frame from the camera.
        Returns the BGR frame, or None if the camera is unavailable.
        """
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return None

            ret, frame = self._cap.read()
            if not ret or frame is None:
                logger.warning("Camera read failed — camera may have disconnected")
                return None

            return frame

    def release(self) -> None:
        """Release the webcam resource."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("Camera released")

    def is_open(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()

    def __del__(self) -> None:
        self.release()
