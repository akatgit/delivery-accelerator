"""Shared helpers for reading the LangGraph checkpoint from API routes
(ARCHITECTURE_v2.0.md section 10). Read-only status/review/artifact/etc.
endpoints open the checkpoint directly rather than going through
`compiled_pipeline()`'s long-lived context manager, since each of these is a
single quick snapshot read, not a graph run.
"""

from __future__ import annotations

import logging

from langgraph.checkpoint.sqlite import SqliteSaver

from backend.config import settings
from backend.graph.pipeline import compile_graph, sqlite_path_from_database_url
from backend.graph.state import PipelineState
from backend.schemas.review import ReviewDomain

logger = logging.getLogger(__name__)


def _sqlite_path() -> str:
    return sqlite_path_from_database_url(settings.database_url)


def graph_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


def get_state_snapshot(session_id: str):
    """Returns the current checkpoint snapshot for a session (`.values` is
    `{}` if the pipeline hasn't started yet)."""
    with SqliteSaver.from_conn_string(_sqlite_path()) as checkpointer:
        graph = compile_graph(checkpointer)
        return graph.get_state(graph_config(session_id))


def get_pipeline_state(session_id: str) -> PipelineState | None:
    """Returns the checkpointed `PipelineState`, or `None` if the pipeline
    hasn't started yet."""
    snapshot = get_state_snapshot(session_id)
    if not snapshot.values:
        return None
    return PipelineState.model_validate(snapshot.values)


def retry_reviewer_domain(session_id: str, domain: ReviewDomain) -> str:
    """Re-runs a single reviewer domain directly against the current
    checkpoint (FR-2.9), without re-running the whole review board. A
    reviewer node is a pure function of `PipelineState` (`graph/nodes.py`),
    so invoking it directly and writing its delta back via `update_state`
    accomplishes a single-domain retry without a full graph re-invocation.

    Returns "retried", "no_pipeline_state" (nothing to retry against), or
    raises `ValueError` for an unknown domain.
    """
    from backend.graph import nodes as graph_nodes

    node_name = f"{domain.value}_reviewer"
    node_fn = getattr(graph_nodes, node_name, None)
    if node_fn is None:
        raise ValueError(f"No reviewer node for domain '{domain.value}'")

    with SqliteSaver.from_conn_string(_sqlite_path()) as checkpointer:
        graph = compile_graph(checkpointer)
        config = graph_config(session_id)
        snapshot = graph.get_state(config)
        if not snapshot.values:
            return "no_pipeline_state"

        state = PipelineState.model_validate(snapshot.values)
        # Drop any prior failure record for this domain so retries don't pile
        # up stale entries every time this endpoint is called.
        state.failed_components = [
            fc for fc in state.failed_components if not fc.component.startswith(f"{domain.value}:")
        ]

        logger.info("retry_reviewer_domain: re-running %s for session %s", node_name, session_id)
        delta = node_fn(state)
        graph.update_state(config, delta)

    return "retried"
