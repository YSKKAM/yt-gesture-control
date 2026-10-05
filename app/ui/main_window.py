"""
app/ui/main_window.py

Main tkinter window for YouTube Gesture Control.
Displays camera status, YouTube status, gesture control toggle,
and last action.

Designed to be hidden (not closed) when the user clicks X,
so the app continues running in the system tray.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Optional

from app.application_state.state import AppState, CameraStatus, YouTubeStatus
from app.logging_setup.logger import get_logger

logger = get_logger(__name__)


# Color palette
_BG = "#1e1e2e"
_FG = "#cdd6f4"
_ACCENT = "#89b4fa"
_GREEN = "#a6e3a1"
_RED = "#f38ba8"
_YELLOW = "#f9e2af"
_PANEL = "#313244"
_BTN_ON = "#a6e3a1"
_BTN_OFF = "#f38ba8"
_BTN_FG = "#1e1e2e"


class MainWindow:
    """
    Creates and manages the main tkinter window.

    Parameters:
        on_toggle_gesture: called when user clicks Enable/Disable
        on_exit: called when user exits from window
    """

    def __init__(
        self,
        on_toggle_gesture: Callable[[bool], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._on_toggle_gesture = on_toggle_gesture
        self._on_exit = on_exit
        self._root: Optional[tk.Tk] = None
        self._gesture_enabled = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Build the window. Must be called from the main thread."""
        root = tk.Tk()
        self._root = root
        root.title("YouTube Gesture Control")
        root.configure(bg=_BG)
        root.resizable(False, False)

        # Intercept window close → hide to tray instead of quitting
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui(root)
        root.geometry("340x320")
        self._center(root)

    def show(self) -> None:
        if self._root:
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()

    def hide(self) -> None:
        if self._root:
            self._root.withdraw()

    def update_state(self, state: AppState) -> None:
        """Called from any thread — schedules a UI update on the main thread."""
        if self._root:
            self._root.after(0, lambda: self._apply_state(state))

    def mainloop(self) -> None:
        if self._root:
            self._root.mainloop()

    def destroy(self) -> None:
        if self._root:
            self._root.quit()
            self._root.destroy()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, root: tk.Tk) -> None:
        pad = {"padx": 16, "pady": 6}

        # Title
        title_frame = tk.Frame(root, bg=_BG)
        title_frame.pack(fill="x", padx=16, pady=(16, 8))
        tk.Label(
            title_frame,
            text="YouTube Gesture Control",
            bg=_BG, fg=_ACCENT,
            font=("Segoe UI", 14, "bold")
        ).pack()

        # Status panel
        status_frame = tk.Frame(root, bg=_PANEL, bd=0, relief="flat")
        status_frame.pack(fill="x", padx=16, pady=4)

        self._cam_dot = tk.Label(status_frame, text="●", bg=_PANEL, fg=_RED, font=("Segoe UI", 11))
        self._cam_dot.grid(row=0, column=0, padx=(12, 4), pady=8)
        self._cam_label = tk.Label(status_frame, text="Camera: Inactive", bg=_PANEL, fg=_FG,
                                   font=("Segoe UI", 10))
        self._cam_label.grid(row=0, column=1, sticky="w", pady=8)

        self._yt_dot = tk.Label(status_frame, text="●", bg=_PANEL, fg=_RED, font=("Segoe UI", 11))
        self._yt_dot.grid(row=1, column=0, padx=(12, 4), pady=(0, 8))
        self._yt_label = tk.Label(status_frame, text="YouTube: Not Connected", bg=_PANEL, fg=_FG,
                                  font=("Segoe UI", 10))
        self._yt_label.grid(row=1, column=1, sticky="w", pady=(0, 8))

        # Toggle button
        btn_frame = tk.Frame(root, bg=_BG)
        btn_frame.pack(fill="x", padx=16, pady=8)

        self._toggle_btn = tk.Button(
            btn_frame,
            text="  Enable Gesture Control  ",
            bg=_BTN_ON, fg=_BTN_FG,
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0, padx=12, pady=6,
            cursor="hand2",
            command=self._on_toggle_clicked
        )
        self._toggle_btn.pack()

        # Legend
        legend_frame = tk.Frame(root, bg=_PANEL)
        legend_frame.pack(fill="x", padx=16, pady=4)

        tk.Label(legend_frame, text="← →  swipe right", bg=_PANEL, fg=_FG,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        tk.Label(legend_frame, text="→  PAUSE", bg=_PANEL, fg=_YELLOW,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=4)

        tk.Label(legend_frame, text="→ ←  swipe left", bg=_PANEL, fg=_FG,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", padx=12, pady=(2, 8))
        tk.Label(legend_frame, text="→  PLAY", bg=_PANEL, fg=_GREEN,
                 font=("Segoe UI", 9, "bold")).grid(row=1, column=1, sticky="w", padx=4)

        # Last action
        action_frame = tk.Frame(root, bg=_BG)
        action_frame.pack(fill="x", padx=16, pady=(8, 4))

        tk.Label(action_frame, text="Last Action:", bg=_BG, fg=_FG,
                 font=("Segoe UI", 9)).pack(side="left")
        self._last_action_label = tk.Label(action_frame, text="—", bg=_BG, fg=_ACCENT,
                                           font=("Segoe UI", 9, "bold"))
        self._last_action_label.pack(side="left", padx=8)

    # ------------------------------------------------------------------
    # State application
    # ------------------------------------------------------------------

    def _apply_state(self, state: AppState) -> None:
        """Must be called on the main thread."""
        # Camera status
        cam_text, cam_color = self._camera_display(state.camera_status)
        self._cam_label.config(text=f"Camera: {cam_text}")
        self._cam_dot.config(fg=cam_color)

        # YouTube status
        yt_text, yt_color = self._yt_display(state.youtube_status)
        self._yt_label.config(text=f"YouTube: {yt_text}")
        self._yt_dot.config(fg=yt_color)

        # Toggle button
        self._gesture_enabled = state.gesture_enabled
        if state.gesture_enabled:
            self._toggle_btn.config(
                text="  Disable Gesture Control  ",
                bg=_BTN_OFF
            )
        else:
            self._toggle_btn.config(
                text="  Enable Gesture Control  ",
                bg=_BTN_ON
            )

        # Last action
        self._last_action_label.config(text=state.last_action)

    @staticmethod
    def _camera_display(status: CameraStatus):
        mapping = {
            CameraStatus.ACTIVE: ("Active", _GREEN),
            CameraStatus.INACTIVE: ("Inactive", _YELLOW),
            CameraStatus.UNAVAILABLE: ("Unavailable", _RED),
            CameraStatus.DISABLED: ("Disabled", _YELLOW),
        }
        return mapping.get(status, ("Unknown", _RED))

    @staticmethod
    def _yt_display(status: YouTubeStatus):
        mapping = {
            YouTubeStatus.CONNECTED: ("Connected", _GREEN),
            YouTubeStatus.DISCONNECTED: ("Not Connected", _RED),
            YouTubeStatus.MULTIPLE_TABS: ("Multiple Tabs", _YELLOW),
            YouTubeStatus.ERROR: ("Error", _RED),
        }
        return mapping.get(status, ("Unknown", _RED))

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _on_toggle_clicked(self) -> None:
        new_state = not self._gesture_enabled
        self._on_toggle_gesture(new_state)

    def _on_close(self) -> None:
        """Hide to tray instead of destroying."""
        self.hide()

    @staticmethod
    def _center(root: tk.Tk) -> None:
        root.update_idletasks()
        w = root.winfo_width()
        h = root.winfo_height()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")
