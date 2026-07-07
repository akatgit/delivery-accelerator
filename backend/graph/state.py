"""LangGraph state schema for the ASDA pipeline (ARCHITECTURE_v2.0.md section 9).

The five review-board nodes run in parallel via ``Send()`` (section 9.1). Each
branch computes its own partial update and LangGraph merges all of them back into
the shared graph state within the same superstep. Any field more than one parallel
branch can write to needs an explicit reducer -- otherwise LangGraph raises a
concurrent-update error the moment two branches both touch it in the same step.
``reviews``, ``failed_components``, and ``decision_log`` are exactly those fields:
every reviewer appends its own review, may log its own failed dimensions, and
records its own skill decisions.

``failed_components`` and ``decision_log`` are pure audit logs -- plain
``operator.add`` (append-only) concatenation is exactly right for them. ``reviews``
is different: after the five reviewers fan out (each contributing a new domain, so
appending is correct there too), a later *sequential* node -- the Review QA Agent
(section 5.4) -- needs to *update* an existing domain's ``ReviewResult`` in place
(e.g. after merging a duplicate finding into another, per FR-2.10.2), not add a
second entry for it. A blind ``operator.add`` would double-count in that case, so
``reviews`` uses ``_merge_reviews`` below: a domain not yet present is appended
(the fan-out case); a domain already present is replaced (the refinement case, and
also the revise-loop case: a domain's review from a fresh iteration supersedes its
prior review rather than accumulating alongside it).
"""

from __future__ import annotations

import operator
from typing import Annotated

from pydantic import Field

from backend.schemas.pipeline import DecisionEntry, FailedComponent
from backend.schemas.project_context import ProjectContext
from backend.schemas.review import ReviewResult


def _merge_reviews(existing: list[ReviewResult], new: list[ReviewResult]) -> list[ReviewResult]:
    """Upsert-by-domain: entries in `new` replace any existing entry for the
    same domain (preserving its original position), or are appended if that
    domain isn't present yet."""
    merged = list(existing)
    index_by_domain = {review.domain: i for i, review in enumerate(merged)}
    for review in new:
        if review.domain in index_by_domain:
            merged[index_by_domain[review.domain]] = review
        else:
            index_by_domain[review.domain] = len(merged)
            merged.append(review)
    return merged


class PipelineState(ProjectContext):
    """``ProjectContext`` extended with LangGraph merge reducers plus a couple of
    session-level inputs that aren't part of the BRD's ProjectContext schema
    (section 12) because they're raw upload inputs, not pipeline outputs.

    All other fields keep ``ProjectContext``'s default "last write wins" behavior,
    which is safe because only one node writes to them in any given superstep.
    """

    reviews: Annotated[list[ReviewResult], _merge_reviews] = Field(default_factory=list)
    failed_components: Annotated[list[FailedComponent], operator.add] = Field(default_factory=list)
    decision_log: Annotated[list[DecisionEntry], operator.add] = Field(default_factory=list)

    raw_documents: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Raw uploaded document content keyed by document type tag "
            "('brd', 'architecture', 'stories', 'tech_preferences' -- FR-1.2), "
            "populated by the API layer before the graph starts. Consumed by "
            "the Document Parsing Agent."
        ),
    )
    standards_dir: str | None = Field(
        default=None,
        description="Filesystem path to the uploaded org standards for this session (section 14.1).",
    )
    generation_plan: dict | None = Field(
        default=None,
        description=(
            "Output of the plan-artifact-generation skill (section 5.6): which "
            "artifact sections to generate, which org standard (if any) feeds "
            "each, and which fall back to defaults. Consumed by the AI Development "
            "Setup Agent (section 5.7). Not part of the BRD's ProjectContext schema "
            "(section 12.3 only persists the resulting "
            "patterns/ai_artifacts/scaffolding_structure, not the plan itself)."
        ),
    )
    consistency_warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Output of the Consistency Checker tool (section 5.8): non-blocking "
            "inconsistency warnings across generated AIArtifacts, shown to the "
            "human at human_gate_2."
        ),
    )
    scaffold_zip_path: str | None = Field(
        default=None,
        description="Filesystem path of the built .zip archive (FR-5.6), set by the build_zip node.",
    )
