"""Runs the compiled pipeline graph in a background thread and broadcasts
stage updates over WebSocket as it progresses (ARCHITECTURE_v2.0.md section
10.2). LangGraph's `.stream()`/`.invoke()` are synchronous, blocking calls,
so each run happens in a worker thread; each update is handed back to the
app's persistent event loop (`ws_manager.get_main_loop()`) via
`run_coroutine_threadsafe` so it can actually `await websocket.send_json(...)`.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from backend.api.graph_access import graph_config
from backend.api.session_store import SessionStore
from backend.api.ws_manager import get_main_loop, ws_manager
from backend.config import settings
from backend.graph.pipeline import compile_graph, sqlite_path_from_database_url
from backend.graph.state import PipelineState

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="asda-pipeline")


def start_pipeline_background(session_id: str, initial_state: PipelineState, store: SessionStore) -> None:
    """Schedules a fresh graph run in a background thread; returns immediately."""
    get_main_loop().run_in_executor(_EXECUTOR, _run_and_broadcast, session_id, initial_state, store)


def resume_pipeline_background(session_id: str, resume_value: dict, store: SessionStore) -> None:
    """Schedules resuming a paused graph (at a human gate) in a background thread."""
    get_main_loop().run_in_executor(_EXECUTOR, _run_and_broadcast, session_id, Command(resume=resume_value), store)


def _run_and_broadcast(session_id: str, graph_input: PipelineState | Command, store: SessionStore) -> None:
    """Runs synchronously in a worker thread; schedules each broadcast back
    onto the app's persistent event loop."""
    try:
        path = sqlite_path_from_database_url(settings.database_url)
        with SqliteSaver.from_conn_string(path) as checkpointer:
            graph = compile_graph(checkpointer)
            config = graph_config(session_id)

            for update in graph.stream(graph_input, config=config, stream_mode="updates"):
                for node_name, node_output in update.items():
                    _handle_node_update(session_id, node_name, node_output, store)

            snapshot = graph.get_state(config)
            final_message = {
                "type": "paused" if snapshot.next else "completed",
                "next": list(snapshot.next),
            }
            _broadcast(session_id, final_message)
    except Exception as exc:  # the pipeline itself already handles its own component-level
        # failures gracefully; this is a last-resort catch for anything that escapes that
        # (e.g. a checkpoint I/O error), so a broken background run is at least reported
        # instead of silently vanishing.
        logger.exception("graph_runner: pipeline run failed for session %s", session_id)
        _broadcast(session_id, {"type": "error", "message": str(exc)})


def _handle_node_update(session_id: str, node_name: str, node_output, store: SessionStore) -> None:
    stage = None
    if isinstance(node_output, dict):
        stage_value = node_output.get("current_stage")
        stage = stage_value.value if hasattr(stage_value, "value") else stage_value

    if stage is not None:
        store.update_session(session_id, current_stage=stage)

    message = {"type": "stage_update", "node": node_name, "stage": stage}
    _broadcast(session_id, message)


def _broadcast(session_id: str, message: dict) -> None:
    asyncio.run_coroutine_threadsafe(ws_manager.broadcast(session_id, message), get_main_loop())
