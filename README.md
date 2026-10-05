# YouTube Gesture Control

Control YouTube playback with a hand gesture — no clicking, no keyboard, no cloud.

## What it does

Wave your hand in front of your webcam:
- **Swipe LEFT → RIGHT** → YouTube **PAUSES**
- **Swipe RIGHT → LEFT** → YouTube **PLAYS**

Works while you're in any other application. YouTube doesn't need to be focused or clicked.

---

## Requirements

- Windows 10 or Windows 11
- Google Chrome or Microsoft Edge
- A webcam (built-in or USB)
- Python 3.9–3.14 (for development) or use the packaged executable

---

## Quick Start (Development)

### 1. Install dependencies

```powershell
python -m pip install -r requirements/requirements.txt
```

### 2. Install the browser extension

1. Open Chrome or Edge
2. Go to `chrome://extensions` (or `edge://extensions`)
3. Enable **Developer Mode** (top right toggle)
4. Click **Load unpacked**
5. Select the `browser_extension/` folder from this project
6. The extension installs. You'll see the YouTube Gesture Control icon.

### 3. Run the desktop app

```powershell
python -m app.main
```

### 4. Use it

1. Open YouTube in Chrome/Edge and start a video
2. In the desktop app, click **Enable Gesture Control**
3. Status shows `Camera: Active` and `YouTube: Connected`
4. Wave your hand:
   - **Left → Right** to pause
   - **Right → Left** to play

---

## Packaged Windows Build

A pre-built executable is provided in `build/dist/` (after building):

```powershell
# Build the executable
python -m PyInstaller build/ytgc.spec

# Run the packaged executable
build\dist\ytgc\ytgc.exe
```

The executable bundles Python and all dependencies. **The user does not need Python installed.**

---

## Project Structure

```
youtube-gesture-control/
├── app/                    # Python desktop application
│   ├── camera/             # Webcam capture
│   ├── hand_tracking/      # MediaPipe hand tracking
│   ├── gesture_detection/  # FSM + validator
│   ├── youtube_control/    # WebSocket server
│   ├── ui/                 # tkinter window
│   ├── system_tray/        # pystray tray icon
│   ├── config/             # Settings loader
│   ├── application_state/  # Shared app state
│   └── logging_setup/      # Rotating file logger
├── browser_extension/      # Chrome/Edge extension
├── tests/                  # Automated + manual tests
├── config/config.yaml      # Tunable parameters
├── requirements/           # Python dependencies
├── docs/                   # Architecture, config, troubleshooting
└── build/                  # PyInstaller spec + output
```

---

## Configuration

Edit `config/config.yaml` to tune gesture sensitivity:

| Parameter | Default | Effect |
|---|---|---|
| `min_displacement_x` | 0.20 | How far hand must move (20% of frame width) |
| `cooldown_ms` | 1000 | Lockout after gesture fires (ms) |
| `max_gesture_duration_ms` | 1500 | Max time for a valid swipe |
| `direction_ratio` | 2.5 | Horizontal must be 2.5× vertical |

See `docs/configuration.md` for the full reference.

---

## Running Tests

```powershell
python -m pip install -r requirements/requirements-dev.txt
python -m pytest tests/ -v
```

All automated tests run without a camera or browser.

---

## Troubleshooting

See `docs/troubleshooting.md` for common issues.

Quick checks:
- **Camera: Unavailable** → Check if another app is using the webcam
- **YouTube: Not Connected** → Check extension is installed and YouTube tab is open on `youtube.com/watch`
- **Gestures not detected** → Lower `min_displacement_x` in `config.yaml`
- **Too many false triggers** → Raise `min_displacement_x` or lower `max_gesture_duration_ms`

---

## Security

- All webcam processing is local. No frames leave your machine.
- The WebSocket server binds to `127.0.0.1` only (localhost).
- No telemetry. No cloud. No accounts.
- Does not require administrator privileges.

---

## Known Limitations

See `docs/troubleshooting.md` for full details.

- YouTube must be on `youtube.com/watch` URL for the extension to activate
- Browser extension requires Developer Mode for sideloaded install (Web Store submission is a future step)
- If MediaPipe fails to load (rare on certain Python versions), falls back to OpenCV skin-color detection — slightly less accurate

---

## Future Features

See `FUTURE_FEATURES.md`.
