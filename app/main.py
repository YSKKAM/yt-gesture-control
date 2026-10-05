"""
app/main.py

Application entry point and orchestrator.

Wires together:
  - Logging
  - Config
  - AppState
  - YouTubeController (WebSocket server)
  - CameraCapture
  - HandTracker
  - GestureStateMachine
  - MainWindow (tkinter)
  - SystemTray (pystray)

Camera processing runs in a dedicated daemon thread.
WebSocket server runs in its own daemon thread.
tkinter mainloop runs on the main thread (required by tkinter).
"""
from __future__ import annotations

import signal
import sys
import threading
import time
from typing import Optional

from app.config.settings import settings
from app.logging_setup.logger import setup_logging, get_logger
from app.application_state.state import app_state, CameraStatus, YouTubeStatus
from app.camera.capture import CameraCapture
from app.hand_tracking.tracker import create_tracker
from app.gesture_detection.state_machine import GestureStateMachine
from app.gesture_detection.validator import GestureDirection
from app.youtube_control.controller import YouTubeController
from app.ui.main_window import MainWindow
from app.system_tray.tray import SystemTray


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Logging
    # ------------------------------------------------------------------
    setup_logging(
        log_file=settings.logging.log_file,
        max_bytes=settings.logging.max_bytes,
        backup_count=settings.logging.backup_count,
        level=settings.logging.level,
    )
    logger = get_logger(__name__)
    logger.info("=== YouTube Gesture Control starting ===")

    # ------------------------------------------------------------------
    # 2. YouTube controller (WebSocket server)
    # ------------------------------------------------------------------
    yt_controller = YouTubeController()
    yt_controller.start()

    # ------------------------------------------------------------------
    # 3. Camera & gesture engine (started/stopped by toggle)
    # ------------------------------------------------------------------
    camera = CameraCapture()
    tracker = create_tracker()

    _camera_thread: Optional[threading.Thread] = None
    _camera_stop_event = threading.Event()

    def _gesture_callback(direction: GestureDirection) -> None:
        """Called by GestureStateMachine when a gesture is confirmed."""
        if direction == GestureDirection.LEFT_TO_RIGHT:
            logger.info("Gesture: LEFT_TO_RIGHT → PAUSE")
            app_state.set_last_gesture("← → (PAUSE)")
            yt_controller.send_action("pause")
        elif direction == GestureDirection.RIGHT_TO_LEFT:
            logger.info("Gesture: RIGHT_TO_LEFT → PLAY")
            app_state.set_last_gesture("→ ← (PLAY)")
            yt_controller.send_action("play")

    fsm = GestureStateMachine(on_gesture=_gesture_callback)

    def _camera_loop(stop_event: threading.Event) -> None:
        """Camera processing loop — runs in its own daemon thread."""
        logger.info("Camera loop starting")

        # Retry opening camera with backoff
        retry_interval = 5
        while not stop_event.is_set():
            if not camera.open():
                logger.warning("Camera unavailable — retrying in %ds", retry_interval)
                app_state.set_camera_status(CameraStatus.UNAVAILABLE)
                stop_event.wait(retry_interval)
                continue

            app_state.set_camera_status(CameraStatus.ACTIVE)
            frame_interval = 1.0 / settings.camera.fps
            fsm.reset()

            while not stop_event.is_set():
                start = time.monotonic()
                frame = camera.read_frame()

                if frame is None:
                    logger.warning("Frame read failed — camera may have disconnected")
                    app_state.set_camera_status(CameraStatus.UNAVAILABLE)
                    camera.release()
                    break

                # Hand tracking + gesture FSM
                hand_pos = tracker.process(frame)
                fsm.update(hand_pos)

                # Throttle to configured FPS
                elapsed = time.monotonic() - start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        camera.release()
        app_state.set_camera_status(CameraStatus.INACTIVE)
        logger.info("Camera loop stopped")

    def _start_gesture_detection() -> None:
        nonlocal _camera_thread
        _camera_stop_event.clear()
        _camera_thread = threading.Thread(
            target=_camera_loop,
            args=(_camera_stop_event,),
            name="ytgc-camera",
            daemon=True
        )
        _camera_thread.start()
        logger.info("Gesture detection ENABLED")

    def _stop_gesture_detection() -> None:
        _camera_stop_event.set()
        camera.release()
        app_state.set_camera_status(CameraStatus.DISABLED)
        fsm.reset()
        logger.info("Gesture detection DISABLED")

    # ------------------------------------------------------------------
    # 4. Toggle callback (from UI or tray)
    # ------------------------------------------------------------------
    def _on_toggle_gesture(enabled: bool) -> None:
        app_state.set_gesture_enabled(enabled)
        if enabled:
            _start_gesture_detection()
        else:
            _stop_gesture_detection()

    # ------------------------------------------------------------------
    # 5. Exit handler
    # ------------------------------------------------------------------
    def _exit_app() -> None:
        logger.info("Application shutting down")
        _stop_gesture_detection()
        yt_controller.stop()
        tray.stop()
        window.destroy()

    # ------------------------------------------------------------------
    # 6. UI components
    # ------------------------------------------------------------------
    window = MainWindow(
        on_toggle_gesture=_on_toggle_gesture,
        on_exit=_exit_app,
    )
    window.build()

    tray = SystemTray(
        on_open=window.show,
        on_toggle_gesture=_on_toggle_gesture,
        on_exit=_exit_app,
    )
    tray.start()

    # Wire state updates to UI and tray
    def _on_state_change(state):
        window.update_state(state)
        tray.update_state(state)

    app_state.register_listener(_on_state_change)

    # Handle Ctrl+C in terminal
    signal.signal(signal.SIGINT, lambda s, f: _exit_app())

    logger.info("Application ready")

    # ------------------------------------------------------------------
    # 7. Main loop (must be on main thread for tkinter)
    # ------------------------------------------------------------------
    window.mainloop()
    logger.info("=== YouTube Gesture Control stopped ===")


if __name__ == "__main__":
    main()
