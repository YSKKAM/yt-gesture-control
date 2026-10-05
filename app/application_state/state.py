"""
app/application_state/state.py

Shared application state observable by UI, tray, and controllers.
Uses a simple thread-safe observer pattern.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional


class CameraStatus(Enum):
    INACTIVE = "Inactive"
    ACTIVE = "Active"
    UNAVAILABLE = "Unavailable"
    DISABLED = "Disabled"


class YouTubeStatus(Enum):
    DISCONNECTED = "Not Connected"
    CONNECTED = "Connected"
    MULTIPLE_TABS = "Multiple Tabs"
    ERROR = "Error"


@dataclass
class AppState:
    """The single source of truth for application status."""
    gesture_enabled: bool = False
    camera_status: CameraStatus = CameraStatus.INACTIVE
    youtube_status: YouTubeStatus = YouTubeStatus.DISCONNECTED
    last_action: str = "—"
    last_gesture: str = "—"


class AppStateManager:
    """
    Thread-safe manager for AppState.
    UI components subscribe to changes via register_listener().
    """

    def __init__(self) -> None:
        self._state = AppState()
        self._lock = threading.Lock()
        self._listeners: List[Callable[[AppState], None]] = []

    def register_listener(self, callback: Callable[[AppState], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    def get_state(self) -> AppState:
        with self._lock:
            # Return a copy
            return AppState(
                gesture_enabled=self._state.gesture_enabled,
                camera_status=self._state.camera_status,
                youtube_status=self._state.youtube_status,
                last_action=self._state.last_action,
                last_gesture=self._state.last_gesture,
            )

    def set_gesture_enabled(self, enabled: bool) -> None:
        self._update(gesture_enabled=enabled)

    def set_camera_status(self, status: CameraStatus) -> None:
        self._update(camera_status=status)

    def set_youtube_status(self, status: YouTubeStatus) -> None:
        self._update(youtube_status=status)

    def set_last_action(self, action: str) -> None:
        self._update(last_action=action)

    def set_last_gesture(self, gesture: str) -> None:
        self._update(last_gesture=gesture)

    def _update(self, **kwargs) -> None:
        with self._lock:
            for key, val in kwargs.items():
                setattr(self._state, key, val)
            state_copy = AppState(
                gesture_enabled=self._state.gesture_enabled,
                camera_status=self._state.camera_status,
                youtube_status=self._state.youtube_status,
                last_action=self._state.last_action,
                last_gesture=self._state.last_gesture,
            )
            listeners = list(self._listeners)

        for cb in listeners:
            try:
                cb(state_copy)
            except Exception:
                pass


# Singleton
app_state = AppStateManager()
