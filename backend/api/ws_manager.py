"""In-process WebSocket connection registry for real-time pipeline updates
(ARCHITECTURE_v2.0.md section 10.2: stage transitions, reviewer completions,
QA progress, scores, errors).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once from `main.py`'s lifespan startup, which runs inside
    uvicorn's single persistent event loop for the app's whole lifetime.
    Background pipeline threads (`graph_runner.py`) schedule their broadcasts
    onto *this* loop rather than whatever loop happened to be running during
    the specific request that kicked off the background run -- capturing the
    latter is fragile (e.g. under `TestClient`, a request's loop can be torn
    down before a slower background thread finishes, making
    `run_coroutine_threadsafe` raise "Event loop is closed")."""
    global _main_loop
    _main_loop = loop


def get_main_loop() -> asyncio.AbstractEventLoop:
    if _main_loop is None:
        raise RuntimeError("Main event loop not set; call set_main_loop() during app startup.")
    return _main_loop


class WebSocketManager:
    """Tracks open WebSocket connections per session and broadcasts JSON
    messages to all of them."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(session_id, set()).add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(session_id)
        if not connections:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        for websocket in list(self._connections.get(session_id, ())):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning("ws_manager: dropping a broken connection for session %s", session_id)
                self.disconnect(session_id, websocket)


ws_manager = WebSocketManager()
