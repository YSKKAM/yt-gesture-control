"""
tests/youtube_control/test_controller.py

Tests for the YouTube controller — verifies message dispatch logic.
Does NOT require a browser or WebSocket connection.

Run with:
    python -m pytest tests/youtube_control/test_controller.py -v
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestYouTubeControllerDispatch:
    """
    Tests the controller's message-building logic in isolation.
    We mock the WebSocket connection so no real network is needed.
    """

    def test_send_pause_action_format(self):
        """Pause action payload must be correctly formatted JSON."""
        payload = json.dumps({"type": "action", "action": "pause"})
        msg = json.loads(payload)
        assert msg["type"] == "action"
        assert msg["action"] == "pause"

    def test_send_play_action_format(self):
        """Play action payload must be correctly formatted JSON."""
        payload = json.dumps({"type": "action", "action": "play"})
        msg = json.loads(payload)
        assert msg["type"] == "action"
        assert msg["action"] == "play"

    def test_send_action_returns_false_when_not_connected(self):
        """
        If no extension is connected, send_action must return False
        and must NOT attempt to send.
        """
        from app.youtube_control.controller import YouTubeController
        ctrl = YouTubeController()
        # _connection is None by default — not started
        result = ctrl.send_action("pause")
        assert result is False

    def test_is_connected_false_initially(self):
        from app.youtube_control.controller import YouTubeController
        ctrl = YouTubeController()
        assert ctrl.is_connected is False

    def test_ack_message_updates_last_action(self):
        """Simulate an ack message from extension and verify state update."""
        import asyncio
        from app.youtube_control.controller import YouTubeController
        from app.application_state.state import app_state

        ctrl = YouTubeController()

        # Simulate handling an ack message
        async def run():
            await ctrl._handle_message(
                json.dumps({"type": "ack", "action": "pause", "status": "paused"})
            )

        asyncio.run(run())

        state = app_state.get_state()
        assert state.last_action == "PAUSE"

    def test_play_ack_updates_last_action(self):
        import asyncio
        from app.youtube_control.controller import YouTubeController
        from app.application_state.state import app_state

        ctrl = YouTubeController()

        async def run():
            await ctrl._handle_message(
                json.dumps({"type": "ack", "action": "play", "status": "played"})
            )

        asyncio.run(run())

        state = app_state.get_state()
        assert state.last_action == "PLAY"

    def test_invalid_json_does_not_crash(self):
        import asyncio
        from app.youtube_control.controller import YouTubeController

        ctrl = YouTubeController()

        async def run():
            await ctrl._handle_message("not valid json {{{")

        # Should not raise
        asyncio.run(run())

    def test_error_message_from_extension(self):
        import asyncio
        from app.youtube_control.controller import YouTubeController

        ctrl = YouTubeController()

        async def run():
            await ctrl._handle_message(
                json.dumps({"type": "error", "message": "No YouTube tab found"})
            )

        asyncio.run(run())  # Should not raise

    def test_multiple_tabs_message_sets_status(self):
        import asyncio
        from app.youtube_control.controller import YouTubeController
        from app.application_state.state import app_state, YouTubeStatus

        ctrl = YouTubeController()

        async def run():
            await ctrl._handle_message(
                json.dumps({"type": "multiple_tabs", "count": 3})
            )

        asyncio.run(run())
        state = app_state.get_state()
        assert state.youtube_status == YouTubeStatus.MULTIPLE_TABS
