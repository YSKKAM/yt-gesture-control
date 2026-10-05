"""
app/system_tray/tray.py

Windows system tray icon using pystray.
Provides: Open/Hide window, Enable/Disable gesture, Status, Exit.
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from app.application_state.state import AppState, CameraStatus, YouTubeStatus
from app.logging_setup.logger import get_logger

logger = get_logger(__name__)


def _make_icon(color: str) -> Image.Image:
    """Generate a simple colored circle icon for the tray."""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Outer circle (border)
    draw.ellipse([2, 2, size - 2, size - 2], fill=color, outline="#ffffff", width=3)
    # Play-like symbol inside
    draw.polygon(
        [(24, 18), (24, 46), (48, 32)],
        fill="#ffffff"
    )
    return img


_ICON_GREEN = _make_icon("#4caf50")   # active
_ICON_GREY = _make_icon("#9e9e9e")    # disabled
_ICON_RED = _make_icon("#f44336")     # error


class SystemTray:
    """
    Runs the pystray tray icon in a background thread.
    """

    def __init__(
        self,
        on_open: Callable[[], None],
        on_toggle_gesture: Callable[[bool], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._on_open = on_open
        self._on_toggle_gesture = on_toggle_gesture
        self._on_exit = on_exit
        self._icon: Optional[pystray.Icon] = None
        self._gesture_enabled = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Build and run the tray icon in a daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            name="ytgc-tray",
            daemon=True
        )
        self._thread.start()

    def update_state(self, state: AppState) -> None:
        """Called from any thread to refresh tray icon and menu."""
        self._gesture_enabled = state.gesture_enabled

        if not state.gesture_enabled:
            icon_img = _ICON_GREY
        elif state.camera_status == CameraStatus.UNAVAILABLE:
            icon_img = _ICON_RED
        else:
            icon_img = _ICON_GREEN

        if self._icon:
            self._icon.icon = icon_img
            # Build tooltip
            cam = state.camera_status.value
            yt = state.youtube_status.value
            gesture = "ON" if state.gesture_enabled else "OFF"
            self._icon.title = f"YouTube Gesture Control\nGesture: {gesture} | Camera: {cam} | YouTube: {yt}"
            self._icon.update_menu()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Open", self._handle_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Gesture Control",
                pystray.Menu(
                    pystray.MenuItem(
                        "Enable",
                        lambda: self._on_toggle_gesture(True),
                        checked=lambda item: self._gesture_enabled,
                        radio=True
                    ),
                    pystray.MenuItem(
                        "Disable",
                        lambda: self._on_toggle_gesture(False),
                        checked=lambda item: not self._gesture_enabled,
                        radio=True
                    ),
                )
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._handle_exit),
        )

        self._icon = pystray.Icon(
            name="ytgc",
            icon=_ICON_GREY,
            title="YouTube Gesture Control",
            menu=menu,
        )
        logger.info("System tray icon started")
        self._icon.run()

    def _handle_open(self, icon=None, item=None) -> None:
        self._on_open()

    def _handle_exit(self, icon=None, item=None) -> None:
        logger.info("Exit requested from system tray")
        self._on_exit()
