# Troubleshooting Guide — YouTube Gesture Control

## Camera Issues

### "Camera: Unavailable"

**Cause:** The webcam is not found, is in use by another app, or failed to initialize.

**Fix:**
1. Check if another application is using the webcam (Teams, Zoom, OBS, etc.) and close it.
2. Unplug and replug your USB webcam.
3. Check Device Manager to confirm the camera is recognized by Windows.
4. Try changing `camera.device_index` in `config/config.yaml` from `0` to `1` if you have multiple cameras.
5. The app retries the camera automatically every 5 seconds — wait and watch the status.

### Camera is detected but hand tracking doesn't work

**Cause:** MediaPipe may have failed to load and fell back to the OpenCV tracker.

**Check:** Look at `logs/ytgc.log` for the line:
```
Using OpenCV skin-color fallback hand tracker
```

**Fix:**
- If on fallback: adjust lighting. The skin-color tracker requires decent lighting and works best against a plain background.
- Try reinstalling mediapipe: `python -m pip install --upgrade mediapipe`

---

## YouTube Connection Issues

### "YouTube: Not Connected"

**Cause:** The browser extension is not installed, not active, or no YouTube tab is open.

**Fix:**
1. Confirm the extension is installed: go to `chrome://extensions` and look for "YouTube Gesture Control".
2. Make sure a YouTube video tab is open at `youtube.com/watch?...` URL (not the homepage).
3. Reload the YouTube tab.
4. Check if the extension is enabled (toggle in extensions page).
5. Check `logs/ytgc.log` for WebSocket connection attempts.

### Extension installed but still not connecting

**Cause:** Port 9876 may be blocked or in use by another application.

**Fix:**
1. Open Task Manager → check if any other app is using port 9876:
   ```powershell
   netstat -ano | findstr :9876
   ```
2. If occupied, change `youtube_control.websocket_port` in `config/config.yaml` to another port (e.g. `9877`).
3. The extension also uses this port — see `browser_extension/background.js` line `const WS_URL = "ws://127.0.0.1:9876"` and update it to match.

---

## Gesture Issues

### Gestures not triggering (too sensitive threshold)

**Cause:** The minimum displacement threshold is too high for your setup.

**Fix:** In `config/config.yaml`, lower `gesture.min_displacement_x` from `0.20` to `0.15`.

### Too many false triggers (random movements pause YouTube)

**Cause:** Threshold is too low.

**Fix:** In `config/config.yaml`:
- Raise `gesture.min_displacement_x` to `0.25`
- Lower `gesture.max_gesture_duration_ms` to `1200`
- Raise `gesture.direction_ratio` to `3.0`

### One swipe triggers twice

**Cause:** Cooldown is too short.

**Fix:** Raise `gesture.cooldown_ms` in `config/config.yaml` (try `1500`).

### Gestures work but YouTube is playing when I swipe left→right

**Cause:** Play/pause is being toggled, not specifically set. This should not happen — the extension reads `video.paused` before acting.

**Check:** Look at `logs/ytgc.log` for ack messages. Check that the extension is the correct version (reload it).

---

## Application Issues

### The app crashes on startup

**Check log:** `logs/ytgc.log` for the error.

**Common causes:**
- Missing package: run `python -m pip install -r requirements/requirements.txt`
- `config/config.yaml` is malformed: delete it and the app will use defaults
- Port 9876 already in use: see above

### System tray icon doesn't appear

**Cause:** pystray may have failed.

**Fix:**
```powershell
python -m pip install --upgrade pystray Pillow
```

### The app window doesn't show after clicking the tray icon

**Cause:** Window may be off-screen (e.g. monitor disconnected).

**Fix:** Edit the registry or restart the app. The window position is not saved between sessions in v1.

---

## Performance Issues

### High CPU usage

**Fix:**
- Lower `camera.fps` in `config/config.yaml` from `20` to `15`
- Lower camera resolution: `camera.width: 480`, `camera.height: 360`
- Close the app when not in use (disable gesture control or use tray → Exit)

---

## Logs

All application events are logged to:
```
logs/ytgc.log
```

Logs rotate at 5MB and keep 3 backups. Check here first for any issue.

To enable more verbose logging, set `logging.level: DEBUG` in `config/config.yaml`.
