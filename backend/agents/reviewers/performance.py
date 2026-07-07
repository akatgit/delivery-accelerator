"""PerformanceReviewer (ARCHITECTURE_v2.0.md section 5.2 routing table).

Pure configuration -- all execution logic lives in BaseReviewer.
"""

from __future__ import annotations

from backend.agents.reviewers.base_reviewer import BaseReviewer
from backend.schemas.review import ReviewDomain
from backend.skills.base import BaseSkill
from backend.skills.review.evaluate_dimension import EvaluateDimensionSkill

ORG_STANDARD_CATEGORIES = ["api_design", "logging"]


class PerformanceReviewer(BaseReviewer):
    """Reviews the performance domain, routed api_design/logging org standards."""

    def __init__(self, skills: list[BaseSkill] | None = None):
        super().__init__(
            name="performance-reviewer",
            domain=ReviewDomain.PERFORMANCE,
            org_standard_categories=ORG_STANDARD_CATEGORIES,
            skills=skills or [EvaluateDimensionSkill()],
        )
