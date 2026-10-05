# Manual Test Plan — YouTube Gesture Control

## Prerequisites
- Desktop app running (gesture control ON)
- Browser extension installed and active
- YouTube open in Chrome or Edge with a video playing or paused
- A second application visible (e.g. VS Code, Notepad) to verify no input leakage

---

## Test 1 — Left → Right → PAUSE

**State before:** YouTube video is playing.

**Action:** Perform a clear, deliberate swipe from left to right in front of the webcam. Move your hand approximately 30–50% of the frame width.

**Expected results:**
- YouTube video pauses.
- Desktop app UI shows: `Last Action: PAUSE`
- VS Code / Notepad receives NO input.

**Pass / Fail:** ____

---

## Test 2 — Right → Left → PLAY

**State before:** YouTube video is paused.

**Action:** Perform a clear, deliberate swipe from right to left in front of the webcam.

**Expected results:**
- YouTube video resumes playing.
- Desktop app UI shows: `Last Action: PLAY`

**Pass / Fail:** ____

---

## Test 3 — Random hand movement does NOT pause

**State before:** YouTube video is playing.

**Action:** Move your hand randomly in front of the webcam (not a deliberate horizontal swipe). Try: small movements, diagonal movements, vertical movements.

**Expected results:**
- YouTube video continues playing.
- No action logged in desktop app.

**Pass / Fail:** ____

---

## Test 4 — Random hand movement does NOT play

**State before:** YouTube video is paused.

**Action:** Move your hand randomly (not a deliberate swipe).

**Expected results:**
- YouTube video remains paused.
- No action logged.

**Pass / Fail:** ____

---

## Test 5 — Control while another app has focus

**State before:** YouTube playing. VS Code (or any other app) is focused/active.

**Action:** WITHOUT clicking on YouTube, perform Left → Right swipe.

**Expected results:**
- YouTube pauses.
- VS Code receives NO spacebar or any other keyboard input.
- No text is typed into VS Code.

**Pass / Fail:** ____

---

## Test 6 — Play while another app has focus

**State before:** YouTube paused. Another app focused.

**Action:** Without clicking YouTube, perform Right → Left swipe.

**Expected results:**
- YouTube resumes.
- Other app receives no input.

**Pass / Fail:** ____

---

## Test 7 — One swipe = exactly one action

**State before:** YouTube playing.

**Action:** Perform one long, slow, deliberate Left → Right swipe.

**Expected results:**
- YouTube pauses exactly ONCE.
- `Last Action` shows PAUSE once.
- No repeated pause/play toggling.

**Pass / Fail:** ____

---

## Test 8 — Cooldown prevents duplicate during the swipe

**State before:** YouTube playing.

**Action:** Perform Left → Right swipe, then immediately (within 1 second) perform another Left → Right swipe.

**Expected results:**
- YouTube pauses once only.
- Second gesture is ignored during cooldown.
- After cooldown (~1 second), gesture detection resumes.

**Pass / Fail:** ____

---

## Test 9 — Camera disconnected

**State before:** App running, gesture control ON.

**Action:** Unplug or disable the webcam.

**Expected results:**
- Desktop app status changes to `Camera: Unavailable`
- App does NOT crash.
- App retries camera every ~5 seconds.
- YouTube status unaffected.

**Pass / Fail:** ____

---

## Test 10 — YouTube tab closed

**State before:** App running, YouTube connected.

**Action:** Close the YouTube browser tab.

**Expected results:**
- Desktop app status changes to `YouTube: Not Connected`
- App does NOT crash.
- Gestures are still detected but no action is sent.

**Pass / Fail:** ____

---

## Test 11 — Gesture control disabled

**State before:** YouTube playing, gesture control ON.

**Action:** Click "Disable Gesture Control" in the app (or via tray menu).

**Action 2:** Perform a clear Left → Right swipe.

**Expected results:**
- YouTube does NOT pause.
- Webcam is released (camera light turns off if indicator light exists).

**Pass / Fail:** ____

---

## Test 12 — System tray operation

**Action:** Click the X button on the main window.

**Expected results:**
- Window hides (not closed).
- Tray icon remains in the taskbar.
- Gesture control continues working in the background.

**Action 2:** Right-click tray icon.

**Expected results:**
- Menu shows: Open, Gesture Control (Enable/Disable), Exit.

**Pass / Fail:** ____

---

## Test 13 — Multiple YouTube tabs

**State before:** Two YouTube tabs open in the browser.

**Action:** Perform Left → Right swipe.

**Expected results:**
- Desktop app shows `YouTube: Multiple Tabs` or similar warning.
- One video pauses (the most recently active tab).
- No crash.

**Pass / Fail:** ____

---

## Tester Notes

Date: ___________
Tester: ___________
OS: ___________
Browser: ___________
Camera: ___________

Overall result: PASS / FAIL
Issues found:
