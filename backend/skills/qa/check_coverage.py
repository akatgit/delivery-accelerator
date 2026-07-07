"""check-coverage skill (ARCHITECTURE_v2.0.md section 5.4; FR-2.10.6).

Evaluates whether it's suspicious that a reviewer returned zero (or very few)
findings for an architecture with known complexity indicators (>5 components,
microservices, distributed systems).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component
from backend.schemas.review import ReviewResult
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/qa/check_coverage.md"


class CoverageWarning(BaseModel):
    """A domain flagged as suspiciously under-covered given this
    architecture's complexity (FR-2.10.6)."""

    domain: str
    warning: str = Field(description="Why zero (or very few) findings from this domain is suspicious.")


class CoverageWarningList(BaseModel):
    """Wraps `list[CoverageWarning]` in an object field for Anthropic's
    tool-use schema (see the extraction skills for why)."""

    items: list[CoverageWarning] = Field(default_factory=list)


def _format_review_summaries(reviews: list[ReviewResult]) -> str:
    if not reviews:
        return "(no reviews completed)"
    return "\n".join(
        f"- [{review.domain.value}] score={review.score}, findings={len(review.findings)}"
        for review in reviews
    )


def _format_components(components: list[Component]) -> str:
    if not components:
        return "(none extracted)"
    return "\n".join(f"- {component.name} ({component.type})" for component in components)


class CheckCoverageSkill(BaseSkill):
    """Flags reviewers whose finding count is suspicious given the
    architecture's complexity (FR-2.10.6)."""

    name = "check-coverage"
    description = "Flags reviewers with suspiciously low finding counts for a complex architecture."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = CoverageWarningList
    use_structured_output = True

    @staticmethod
    def build_inputs(reviews: list[ReviewResult], components: list[Component]) -> dict:
        return {
            "review_summaries": _format_review_summaries(reviews),
            "component_count": len(components),
            "components_summary": _format_components(components),
        }
