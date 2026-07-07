"""The pipeline StateGraph (ARCHITECTURE_v2.0.md section 9).

    START
      -> parse_documents
      -> detect_standard_conflicts
      -> route_to_reviewers (Send() fan-out to 5 parallel reviewer nodes)
      -> aggregate_reviews
      -> review_qa
      -> human_gate_1 (dynamic interrupt() inside the node -- see graph/nodes.py)
           revise -> parse_documents
           accept/override -> synthesize_context
      -> synthesize_context
      -> generate_ai_artifacts
      -> consistency_check
      -> generate_scaffolding
      -> human_gate_2 (dynamic interrupt() inside the node -- see graph/nodes.py)
           reject -> synthesize_context
           accept -> build_zip
      -> build_zip
      -> END

Note on gate 2's "reject": section 9.1's diagram uses the word REJECT for
human_gate_2, but the HumanDecision schema (BRD_v2.0.md section 12.4) only
defines "accept" | "override" | "revise" | "resolve_contradiction" — there is no
separate reject value, and that schema is authoritative. REJECT at gate 2 is
therefore modeled as the existing REVISE action; both mean "send this back for
rework," just at a different point in the pipeline.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Send

from backend.config import settings
from backend.graph import nodes
from backend.graph.state import PipelineState
from backend.schemas.pipeline import HumanDecisionAction

REVIEWER_NODES = [
    "architecture_reviewer",
    "security_reviewer",
    "performance_reviewer",
    "reliability_reviewer",
    "compliance_reviewer",
]


def route_to_reviewers(state: PipelineState) -> list[Send]:
    """Fan out to the five review-board nodes in parallel (section 9.1).

    Each reviewer node instantiates and runs its real `BaseReviewer` subclass
    (see `graph/nodes.py`), which mutates its `state` argument in place. Each
    `Send` gets its own deep copy of `state` rather than sharing one object
    across all five branches, so no reviewer's in-place mutations (appending
    to `reviews`, `decision_log`, etc.) can be observed by, or interleave
    with, another reviewer's -- each branch's before/after snapshots for its
    reducer-field deltas stay correct regardless of how LangGraph schedules
    the five branches.
    """
    return [Send(reviewer, state.model_copy(deep=True)) for reviewer in REVIEWER_NODES]


def _latest_decision(state: PipelineState):
    return state.human_decisions[-1] if state.human_decisions else None


def route_after_human_gate_1(state: PipelineState) -> str:
    """revise -> re-run extraction; accept/override -> proceed to synthesis.

    Defaults to proceeding when no decision is recorded yet, which only happens
    if this is invoked outside the normal interrupt/resume flow (e.g. ad hoc
    testing without a human decision in the loop)."""
    decision = _latest_decision(state)
    if decision is not None and decision.action == HumanDecisionAction.REVISE:
        return "parse_documents"
    return "synthesize_context"


def route_after_human_gate_2(state: PipelineState) -> str:
    """reject (modeled as revise, see module docstring) -> regenerate from
    synthesis; accept -> build the final zip."""
    decision = _latest_decision(state)
    if decision is not None and decision.action == HumanDecisionAction.REVISE:
        return "synthesize_context"
    return "build_zip"


def build_graph() -> StateGraph:
    """Assemble the pipeline StateGraph. Does not compile it — callers choose
    the checkpointer (see ``compiled_pipeline`` below)."""
    builder = StateGraph(PipelineState)

    builder.add_node("parse_documents", nodes.parse_documents)
    builder.add_node("detect_standard_conflicts", nodes.detect_standard_conflicts)
    builder.add_node("architecture_reviewer", nodes.architecture_reviewer)
    builder.add_node("security_reviewer", nodes.security_reviewer)
    builder.add_node("performance_reviewer", nodes.performance_reviewer)
    builder.add_node("reliability_reviewer", nodes.reliability_reviewer)
    builder.add_node("compliance_reviewer", nodes.compliance_reviewer)
    builder.add_node("aggregate_reviews", nodes.aggregate_reviews)
    builder.add_node("review_qa", nodes.review_qa)
    builder.add_node("human_gate_1", nodes.human_gate_1)
    builder.add_node("synthesize_context", nodes.synthesize_context)
    builder.add_node("generate_ai_artifacts", nodes.generate_ai_artifacts)
    builder.add_node("consistency_check", nodes.consistency_check)
    builder.add_node("generate_scaffolding", nodes.generate_scaffolding)
    builder.add_node("human_gate_2", nodes.human_gate_2)
    builder.add_node("build_zip", nodes.build_zip)

    builder.add_edge(START, "parse_documents")
    builder.add_edge("parse_documents", "detect_standard_conflicts")
    builder.add_conditional_edges("detect_standard_conflicts", route_to_reviewers, REVIEWER_NODES)

    for reviewer in REVIEWER_NODES:
        builder.add_edge(reviewer, "aggregate_reviews")

    # aggregate_reviews -> review_qa -> human_gate_1 must run in exactly this
    # order: QA validates the aggregated review before the human ever sees it.
    builder.add_edge("aggregate_reviews", "review_qa")
    builder.add_edge("review_qa", "human_gate_1")
    builder.add_conditional_edges(
        "human_gate_1",
        route_after_human_gate_1,
        ["parse_documents", "synthesize_context"],
    )

    builder.add_edge("synthesize_context", "generate_ai_artifacts")
    builder.add_edge("generate_ai_artifacts", "consistency_check")
    builder.add_edge("consistency_check", "generate_scaffolding")
    builder.add_edge("generate_scaffolding", "human_gate_2")
    builder.add_conditional_edges(
        "human_gate_2",
        route_after_human_gate_2,
        ["synthesize_context", "build_zip"],
    )

    builder.add_edge("build_zip", END)

    return builder


def compile_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Compile the graph with the given checkpointer.

    Neither human gate needs ``interrupt_before`` (section 9.2's original
    static-pause design): both now call the dynamic ``interrupt()`` themselves
    (see ``graph/nodes.py``), which already pauses execution *inside* the
    node. Listing them in ``interrupt_before`` as well would pause the graph a
    second time before the node even runs, requiring an extra no-op resume to
    reach the node's own interrupt() call.
    """
    return build_graph().compile(checkpointer=checkpointer)


def sqlite_path_from_database_url(database_url: str) -> str:
    """``settings.database_url`` is a SQLAlchemy-style URL (e.g.
    ``sqlite:///./pipeline_state.db``); ``SqliteSaver`` wants a plain sqlite3
    connection string. Public because the API layer (``backend/api/graph_access.py``)
    needs to open the same checkpoint database read-only for status/review/etc.
    endpoints, without going through ``compiled_pipeline()``'s context manager."""
    prefix = "sqlite:///"
    return database_url[len(prefix) :] if database_url.startswith(prefix) else database_url


@contextmanager
def compiled_pipeline() -> Iterator[CompiledStateGraph]:
    """Yield a compiled pipeline graph backed by the SQLite checkpointer at
    ``settings.database_url`` (section 9.2).

    Usage::

        with compiled_pipeline() as graph:
            graph.invoke(initial_state, config={"configurable": {"thread_id": session_id}})
    """
    path = sqlite_path_from_database_url(settings.database_url)
    with SqliteSaver.from_conn_string(path) as checkpointer:
        yield compile_graph(checkpointer)
