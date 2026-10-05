"""
app/youtube_control/controller.py

WebSocket server that the browser extension connects to.

Architecture:
  Desktop App (this module)  ←→ ws://localhost:PORT ←→ Browser Extension
  
The extension is a WebSocket CLIENT.
This module is the WebSocket SERVER.

Protocol (JSON):
  Desktop → Extension:
    {"type": "action", "action": "pause"}
    {"type": "action", "action": "play"}
    {"type": "ping"}

  Extension → Desktop:
    {"type": "connected", "tab_id": 123, "tab_title": "..."}
    {"type": "disconnected"}
    {"type": "ack", "action": "pause", "status": "paused"}
    {"type": "ack", "action": "play", "status": "played"}
    {"type": "ack", "action": "play", "status": "already_correct"}
    {"type": "error", "message": "..."}
    {"type": "pong"}
    {"type": "multiple_tabs", "count": N}
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Callable, Optional

import websockets
import websockets.server

from app.application_state.state import app_state, YouTubeStatus
from app.config.settings import settings
from app.logging_setup.logger import get_logger

logger = get_logger(__name__)


class YouTubeController:
    """
    Runs an asyncio WebSocket server in a background daemon thread.
    Exposes synchronous send_action(action) to the gesture pipeline.
    """

    def __init__(self) -> None:
        self._port = settings.youtube_control.websocket_port
        self._connection: Optional[websockets.server.WebSocketServerProtocol] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API (called from main/gesture thread)
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the WebSocket server in a background thread."""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_server_thread,
            name="ytgc-ws-server",
            daemon=True
        )
        self._thread.start()
        logger.info("YouTube controller WebSocket server starting on port %d", self._port)

    def stop(self) -> None:
        """Stop the server."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def send_action(self, action: str) -> bool:
        """
        Send 'play' or 'pause' to the connected extension.
        Thread-safe. Returns True if message was queued, False if not connected.
        """
        with self._lock:
            conn = self._connection
            loop = self._loop

        if conn is None or loop is None:
            logger.warning("Cannot send action '%s': extension not connected", action)
            return False

        payload = json.dumps({"type": "action", "action": action})
        asyncio.run_coroutine_threadsafe(self._send(conn, payload), loop)
        logger.info("Action dispatched: %s", action)
        return True

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connection is not None

    # ------------------------------------------------------------------
    # Internal — asyncio server
    # ------------------------------------------------------------------

    def _run_server_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as exc:
            logger.error("WebSocket server error: %s", exc)
        finally:
            self._loop.close()

    async def _serve(self) -> None:
        # ping_interval=None: Chrome/Edge extension service workers cannot respond
        # to WebSocket-level pings, causing connections to drop every ~60s.
        # Application-level heartbeat is handled by the extension's background.js instead.
        async with websockets.serve(
            self._handle_connection,
            "127.0.0.1",   # localhost only — no external exposure
            self._port,
            ping_interval=None,
            ping_timeout=None,
        ):
            logger.info("WebSocket server listening on ws://127.0.0.1:%d", self._port)
            while self._running:
                await asyncio.sleep(0.5)

    async def _handle_connection(
        self,
        websocket: websockets.server.WebSocketServerProtocol
    ) -> None:
        """Handle one extension connection."""
        with self._lock:
            self._connection = websocket

        logger.info("Browser extension connected from %s", websocket.remote_address)
        app_state.set_youtube_status(YouTubeStatus.CONNECTED)

        try:
            async for raw in websocket:
                await self._handle_message(raw)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Browser extension disconnected")
        except Exception as exc:
            logger.error("WebSocket connection error: %s", exc)
        finally:
            with self._lock:
                if self._connection is websocket:
                    self._connection = None
            app_state.set_youtube_status(YouTubeStatus.DISCONNECTED)
            logger.info("YouTube status: DISCONNECTED")

    async def _handle_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON from extension: %s", raw[:100])
            return

        msg_type = msg.get("type", "")

        if msg_type == "connected":
            tab_title = msg.get("tab_title", "unknown tab")
            logger.info("YouTube tab active: '%s'", tab_title)
            app_state.set_youtube_status(YouTubeStatus.CONNECTED)

        elif msg_type == "multiple_tabs":
            count = msg.get("count", "?")
            logger.warning("Multiple YouTube tabs detected (%s) — controlling most recent", count)
            app_state.set_youtube_status(YouTubeStatus.MULTIPLE_TABS)

        elif msg_type == "ack":
            action = msg.get("action", "")
            status = msg.get("status", "")
            logger.info("Action acknowledged: action=%s status=%s", action, status)
            if status in ("paused", "played"):
                app_state.set_last_action(action.upper())

        elif msg_type == "error":
            logger.error("Extension error: %s", msg.get("message", "unknown"))
            app_state.set_last_action("Error")

        elif msg_type == "pong":
            pass  # heartbeat response, no action needed

        elif msg_type == "disconnected":
            app_state.set_youtube_status(YouTubeStatus.DISCONNECTED)

        else:
            logger.debug("Unknown message type from extension: %s", msg_type)

    @staticmethod
    async def _send(websocket, payload: str) -> None:
        try:
            await websocket.send(payload)
        except Exception as exc:
            logger.error("Failed to send to extension: %s", exc)
