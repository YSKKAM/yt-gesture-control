# Architecture — YouTube Gesture Control

## Overview

YouTube Gesture Control is a Windows desktop application that detects horizontal hand gestures via webcam and maps them to YouTube play/pause commands.

The key architectural constraint is: **YouTube must be controlled without affecting any other focused application.** This rules out keyboard simulation. The solution is a desktop app ↔ browser extension channel over a local WebSocket.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Windows Desktop App (Python)              │
│                                                              │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  Camera   │───▶│ Hand Tracker │───▶│ Gesture FSM +    │  │
│  │ (OpenCV)  │    │ (MediaPipe)  │    │ Validator        │  │
│  └───────────┘    └──────────────┘    └────────┬─────────┘  │
│                                                │             │
│                                       ┌────────▼─────────┐  │
│  ┌─────────┐    ┌───────────────┐    │ Action Controller │  │
│  │  tray   │◀──│   App State   │◀──│                   │  │
│  │  icon   │    │   Manager     │    └────────┬─────────┘  │
│  └─────────┘    └───────────────┘             │             │
│  ┌─────────┐           ▲             ┌────────▼─────────┐  │
│  │  tkint  │───────────┘             │ YouTube          │  │
│  │  window │                         │ Controller       │  │
│  └─────────┘                         │ (WS Server)      │  │
│                                       └────────┬─────────┘  │
└────────────────────────────────────────────────│─────────────┘
                                                 │ ws://127.0.0.1:9876
                              ┌──────────────────▼──────────────────┐
                              │      Browser Extension (JS)          │
                              │                                      │
                              │  background.js (Service Worker)      │
                              │   - WebSocket client                 │
                              │   - Tab management                   │
                              │   - chrome.scripting.executeScript   │
                              └──────────────────┬───────────────────┘
                                                 │ executeScript
                              ┌──────────────────▼───────────────────┐
                              │      YouTube Tab (Browser)            │
                              │                                       │
                              │  video.pause() / video.play()        │
                              │  Reads video.paused before acting    │
                              └───────────────────────────────────────┘
```

---

## Component Descriptions

### Camera Capture (`app/camera/capture.py`)
- Wraps `cv2.VideoCapture` with thread-safe open/read/release
- Configures resolution (640×480) and FPS (20) to minimize CPU usage
- Sets buffer size to 1 to avoid stale frames
- Returns `None` on read failure — never crashes the camera thread

### Hand Tracker (`app/hand_tracking/tracker.py`)
- Primary: MediaPipe Hands (local, CPU-only, no cloud)
- Fallback: OpenCV YCrCb skin-color segmentation (if MediaPipe unavailable)
- Returns normalized `HandPosition(x, y, confidence)` per frame
- Tracking landmark: middle finger base (landmark 9) — stable across hand orientations

### Gesture Validator (`app/gesture_detection/validator.py`)
- Pure function: `validate_gesture(trajectory) → ValidationResult`
- No side effects, fully unit-testable without any hardware
- Validates: displacement, duration, speed, direction dominance, no reversal
- All coordinates normalized (0.0–1.0) — resolution-independent

### Gesture State Machine (`app/gesture_detection/state_machine.py`)
- States: `IDLE → HAND_DETECTED → TRACKING → COOLDOWN → IDLE`
- Prevents repeated triggers from a single swipe via COOLDOWN state
- Validates trajectory on hand-lost OR during tracking (whichever comes first)
- Fires `on_gesture(GestureDirection)` callback — exactly once per gesture

### Application State (`app/application_state/state.py`)
- Singleton `AppStateManager` with observer pattern
- Thread-safe: all state changes via `set_*` methods
- UI and tray register listeners — updated automatically on state change

### YouTube Controller (`app/youtube_control/controller.py`)
- Runs an asyncio WebSocket server on `127.0.0.1:9876` in a daemon thread
- Exposes synchronous `send_action("play"/"pause")` to gesture pipeline
- Handles: connection, disconnection, ack, error, multiple-tabs messages
- Updates AppState on connection changes

### Browser Extension (`browser_extension/`)
- Manifest V3, Chrome and Edge compatible
- Service worker (`background.js`) maintains WebSocket connection to desktop app
- Reconnects with exponential backoff (1s → 2s → 4s → max 30s)
- Manages "active YouTube tab" concept — uses most recently focused tab if multiple
- Uses `chrome.scripting.executeScript` to run `video.pause()`/`video.play()` directly
- Reads `video.paused` before acting — no blind toggle

### Main Window (`app/ui/main_window.py`)
- tkinter window (required to run on main thread)
- Hides to tray on X button — does not quit
- Receives state updates via `AppState` listener → schedules via `root.after(0, ...)`

### System Tray (`app/system_tray/tray.py`)
- pystray icon in daemon thread
- Icon color: green (active), grey (disabled), red (camera error)
- Right-click menu: Open, Enable/Disable, Exit

---

## Threading Model

| Thread | Name | Purpose |
|---|---|---|
| Main | Main | tkinter mainloop (required) |
| Daemon | `ytgc-camera` | Camera read + hand tracking + FSM |
| Daemon | `ytgc-ws-server` | asyncio event loop for WebSocket server |
| Daemon | `ytgc-tray` | pystray tray icon event loop |

The gesture callback is called from `ytgc-camera`. It calls `YouTubeController.send_action()` which uses `asyncio.run_coroutine_threadsafe` to safely cross the thread boundary into the asyncio event loop.

---

## Communication Protocol

### Desktop → Extension
```json
{"type": "action", "action": "pause"}
{"type": "action", "action": "play"}
{"type": "ping"}
```

### Extension → Desktop
```json
{"type": "connected", "tab_id": 123, "tab_title": "Video Title - YouTube"}
{"type": "disconnected"}
{"type": "ack", "action": "pause", "status": "paused"}
{"type": "ack", "action": "play", "status": "played"}
{"type": "ack", "action": "play", "status": "already_correct"}
{"type": "error", "message": "No YouTube tab found"}
{"type": "multiple_tabs", "count": 2}
{"type": "pong"}
```

### Status values in ack
- `"paused"` — video was playing, now paused
- `"played"` — video was paused, now playing
- `"already_correct"` — video was already in the requested state, no action taken
- `"no_video"` — no `<video>` element found on the page

---

## Design Decisions

### Why WebSocket + Extension instead of keyboard simulation?
Keyboard simulation (`pyautogui`, `pywin32 SendKeys`) sends input to the **focused window**, not to YouTube specifically. The spec's hardest requirement is: gesture → YouTube only, no other app affected. The extension directly calls `video.pause()` / `video.play()` on the DOM element — zero keyboard events, works regardless of focus.

### Why MediaPipe over other hand detectors?
- Runs 100% locally — no camera frames leave the machine
- CPU-only mode is efficient enough at 640×480 @ 20fps
- Returns stable normalized landmark coordinates
- Actively maintained, widely tested

### Why normalized coordinates?
Gesture thresholds (e.g. `min_displacement_x: 0.20`) are fractions of frame size. This makes the same config work across different webcam resolutions.

### Why tkinter over PyQt / PySide?
tkinter is built into Python — zero extra dependency, zero licensing concern. The UI is simple enough that tkinter is sufficient.
