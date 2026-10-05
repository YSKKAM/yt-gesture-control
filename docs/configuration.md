# Configuration Reference — YouTube Gesture Control

All settings are in `config/config.yaml`.

---

## `gesture` — Gesture Detection Thresholds

All x/y values are **normalized** (0.0–1.0 as fraction of frame width/height).

| Key | Default | Type | Description |
|---|---|---|---|
| `min_displacement_x` | `0.20` | float | Minimum horizontal travel required. 0.20 = 20% of frame width. Lower = more sensitive, higher = requires bigger swipe. |
| `max_displacement_y` | `0.12` | float | Maximum vertical drift allowed. Movements more vertical than this are rejected. |
| `direction_ratio` | `2.5` | float | Horizontal displacement must be ≥ this multiple of vertical displacement. Prevents diagonal gestures triggering. |
| `min_speed` | `0.15` | float | Minimum average speed (normalized units/second). Prevents slow accidental drift. |
| `max_gesture_duration_ms` | `1500` | int | Maximum gesture duration in milliseconds. Gestures taking longer are rejected. |
| `min_gesture_duration_ms` | `120` | int | Minimum gesture duration. Prevents single-frame spikes. |
| `cooldown_ms` | `1000` | int | Lockout period after a gesture fires (ms). Prevents one physical swipe triggering twice. |
| `min_stable_frames` | `3` | int | Frames with hand detected before tracking starts. Prevents triggering from hand appearing suddenly. |

### Tuning Guide

**Too sensitive (false triggers)?**
- Raise `min_displacement_x` (e.g. `0.25`)
- Lower `max_gesture_duration_ms` (e.g. `1200`)
- Raise `direction_ratio` (e.g. `3.0`)

**Not sensitive enough (missing gestures)?**
- Lower `min_displacement_x` (e.g. `0.15`)
- Raise `max_gesture_duration_ms` (e.g. `1800`)
- Lower `min_speed` (e.g. `0.10`)

**One swipe triggers twice?**
- Raise `cooldown_ms` (e.g. `1500`)

---

## `camera` — Camera Settings

| Key | Default | Type | Description |
|---|---|---|---|
| `device_index` | `0` | int | Webcam device index. 0 = first camera. Change to 1, 2, etc. if multiple cameras. |
| `width` | `640` | int | Capture width in pixels. Lower = less CPU. |
| `height` | `480` | int | Capture height in pixels. |
| `fps` | `20` | int | Target frames per second. Lower = less CPU. Don't go below 10. |

---

## `hand_tracking` — MediaPipe Parameters

| Key | Default | Type | Description |
|---|---|---|---|
| `min_detection_confidence` | `0.75` | float | Confidence threshold for initial hand detection (0–1). Lower = more detections (including false), higher = fewer but more reliable. |
| `min_tracking_confidence` | `0.70` | float | Confidence threshold for tracking between frames. |
| `tracking_landmark` | `9` | int | Which MediaPipe hand landmark to track (0=wrist, 9=middle finger base, 12=middle finger tip). |

---

## `youtube_control` — WebSocket / Extension

| Key | Default | Type | Description |
|---|---|---|---|
| `websocket_port` | `9876` | int | Port the desktop app listens on. Must match `WS_URL` in `browser_extension/background.js`. |
| `heartbeat_interval_s` | `5` | int | WebSocket ping interval in seconds. Detects stale connections. |

> **Important:** If you change `websocket_port`, also update the `WS_URL` constant in `browser_extension/background.js` and reload the extension.

---

## `logging` — Log Settings

| Key | Default | Type | Description |
|---|---|---|---|
| `log_file` | `logs/ytgc.log` | str | Log file path (relative to project root). |
| `max_bytes` | `5242880` | int | Max log file size before rotation (5 MB). |
| `backup_count` | `3` | int | Number of rotated log files to keep. |
| `level` | `INFO` | str | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`. Use `DEBUG` to see all gesture decisions. |
