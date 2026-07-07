"""WebSocket endpoint for real-time pipeline updates (ARCHITECTURE_v2.0.md
section 10.2): stage transitions, reviewer completions, QA progress, scores,
errors -- broadcast by `graph_runner.py` as the background pipeline run
progresses.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.ws_manager import ws_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/api/sessions/{session_id}/stream")
async def stream_session(websocket: WebSocket, session_id: str) -> None:
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            # Clients don't need to send anything -- this just keeps the
            # connection open so ws_manager.broadcast() can push updates to it.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
