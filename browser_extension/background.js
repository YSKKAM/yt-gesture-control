/**
 * background.js — Service Worker
 *
 * Connects to the desktop app WebSocket server (ws://127.0.0.1:9876).
 * Manages the "active YouTube tab" concept.
 * Dispatches play/pause commands to the correct tab via chrome.scripting.
 *
 * Protocol:
 *   Receives: {"type": "action", "action": "pause"} or {"action": "play"}
 *   Sends:    {"type": "connected", "tab_id": N, "tab_title": "..."}
 *             {"type": "ack", "action": "...", "status": "..."}
 *             {"type": "error", "message": "..."}
 *             {"type": "multiple_tabs", "count": N}
 *             {"type": "pong"}
 */

const WS_URL = "ws://127.0.0.1:9876";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const KEEPALIVE_INTERVAL_MS = 20000; // Send keepalive every 20s to prevent service worker termination

let ws = null;
let activeYouTubeTabId = null;
let reconnectDelay = RECONNECT_BASE_MS;
let reconnectTimer = null;
let keepaliveTimer = null;

// Keep the service worker alive so the WebSocket connection isn't dropped
// Chrome MV3 service workers terminate after ~30s of inactivity
function startKeepalive() {
  if (keepaliveTimer) clearInterval(keepaliveTimer);
  keepaliveTimer = setInterval(() => {
    // Sending a message to chrome runtime keeps the service worker alive
    chrome.runtime.getPlatformInfo(() => {});
    // Also send a ping to the desktop app
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "ping" }));
    }
  }, KEEPALIVE_INTERVAL_MS);
}


// ---------------------------------------------------------------------------
// WebSocket connection management
// ---------------------------------------------------------------------------

function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return;
  }

  console.log("[YTGC] Connecting to desktop app at", WS_URL);
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log("[YTGC] Connected to desktop app");
    reconnectDelay = RECONNECT_BASE_MS;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    // Start keepalive to prevent service worker from being terminated
    startKeepalive();
    // Notify desktop app of current YouTube tab
    notifyCurrentTab();
  };

  ws.onmessage = (event) => {
    handleMessage(event.data);
  };

  ws.onerror = (err) => {
    console.warn("[YTGC] WebSocket error:", err);
  };

  ws.onclose = () => {
    console.log("[YTGC] Disconnected from desktop app — reconnecting in", reconnectDelay, "ms");
    ws = null;
    scheduleReconnect();
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    reconnectDelay = Math.min(reconnectDelay * 2, RECONNECT_MAX_MS);
    connect();
  }, reconnectDelay);
}

function send(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
  }
}

// ---------------------------------------------------------------------------
// Message handling
// ---------------------------------------------------------------------------

async function handleMessage(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch (e) {
    console.warn("[YTGC] Invalid JSON from desktop app:", raw);
    return;
  }

  if (msg.type === "ping") {
    send({ type: "pong" });
    return;
  }

  if (msg.type === "action") {
    const action = msg.action;
    if (action !== "play" && action !== "pause") {
      send({ type: "error", message: `Unknown action: ${action}` });
      return;
    }
    await executeYouTubeAction(action);
  }
}

// ---------------------------------------------------------------------------
// YouTube tab management
// ---------------------------------------------------------------------------

async function findYouTubeTabs() {
  const tabs = await chrome.tabs.query({ url: "https://www.youtube.com/watch*" });
  return tabs;
}

async function notifyCurrentTab() {
  const tabs = await findYouTubeTabs();

  if (tabs.length === 0) {
    activeYouTubeTabId = null;
    send({ type: "disconnected" });
    return;
  }

  if (tabs.length > 1) {
    // Use the most recently focused one — find by lastAccessed
    const sorted = tabs.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0));
    activeYouTubeTabId = sorted[0].id;
    send({ type: "multiple_tabs", count: tabs.length });
    send({
      type: "connected",
      tab_id: activeYouTubeTabId,
      tab_title: sorted[0].title || "YouTube"
    });
  } else {
    activeYouTubeTabId = tabs[0].id;
    send({
      type: "connected",
      tab_id: activeYouTubeTabId,
      tab_title: tabs[0].title || "YouTube"
    });
  }
}

// ---------------------------------------------------------------------------
// YouTube playback control
// ---------------------------------------------------------------------------

async function executeYouTubeAction(action) {
  // Refresh active tab — user may have opened/closed tabs
  const tabs = await findYouTubeTabs();

  if (tabs.length === 0) {
    console.log("[YTGC] No YouTube tab found — cannot execute:", action);
    send({ type: "error", message: "No YouTube tab found" });
    activeYouTubeTabId = null;
    return;
  }

  let targetTab;
  if (activeYouTubeTabId !== null) {
    targetTab = tabs.find(t => t.id === activeYouTubeTabId);
  }
  if (!targetTab) {
    // Fall back to most recent
    const sorted = tabs.sort((a, b) => (b.lastAccessed || 0) - (a.lastAccessed || 0));
    targetTab = sorted[0];
    activeYouTubeTabId = targetTab.id;
  }

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: targetTab.id },
      func: controlYouTube,
      args: [action]
    });

    const result = results && results[0] && results[0].result;
    console.log("[YTGC] Action result:", action, result);
    send({
      type: "ack",
      action: action,
      status: result ? result.status : "unknown"
    });
  } catch (err) {
    console.error("[YTGC] Script execution failed:", err);
    send({ type: "error", message: err.message });
  }
}

/**
 * This function is injected into the YouTube tab.
 * It runs in the page context and controls the video element directly.
 * It checks playback state before acting — no blind toggle.
 */
function controlYouTube(action) {
  const video = document.querySelector("video");
  if (!video) {
    return { status: "no_video" };
  }

  if (action === "pause") {
    if (!video.paused) {
      video.pause();
      return { status: "paused" };
    } else {
      return { status: "already_correct" };
    }
  }

  if (action === "play") {
    if (video.paused) {
      video.play().catch(() => {});
      return { status: "played" };
    } else {
      return { status: "already_correct" };
    }
  }

  return { status: "unknown_action" };
}

// ---------------------------------------------------------------------------
// Tab event listeners — keep activeYouTubeTabId current
// ---------------------------------------------------------------------------

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url && tab.url.includes("youtube.com/watch")) {
    activeYouTubeTabId = tabId;
    send({ type: "connected", tab_id: tabId, tab_title: tab.title || "YouTube" });
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeYouTubeTabId) {
    activeYouTubeTabId = null;
    console.log("[YTGC] Active YouTube tab closed");
    // Check if other YouTube tabs exist
    notifyCurrentTab();
  }
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (tab.url && tab.url.includes("youtube.com/watch")) {
      activeYouTubeTabId = tabId;
    }
  } catch (e) {}
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
connect();
