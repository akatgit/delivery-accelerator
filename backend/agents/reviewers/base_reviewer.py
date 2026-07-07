"""BaseReviewer: shared execution pattern for the five domain reviewer agents
(ARCHITECTURE_v2.0.md section 5.2).

Concrete reviewers (architecture, security, performance, reliability, compliance)
subclass this and only need to supply their domain, org_standard_categories, rubric,
and the ``evaluate-dimension`` skill instance — all evaluation logic lives here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.agents.base import BaseAgent
from backend.rubrics.loader import load_rubric
from backend.schemas.project_context import ProjectContext
from backend.schemas.review import DimensionScore, Finding, ReviewDomain, ReviewResult, ReviewRubric
from backend.skills.base import BaseSkill

logger = logging.getLogger(__name__)

EVALUATE_DIMENSION_SKILL = "evaluate-dimension"


class BaseReviewer(BaseAgent):
    """Shared implementation for all five parallel review-board agents.

    Each dimension in the rubric is evaluated independently via the
    ``evaluate-dimension`` skill, so a single dimension failing does not sink the
    whole domain review — the reviewer continues with the remaining dimensions and
    the domain score is the average of whatever completed successfully.
    """

    domain: ReviewDomain
    rubric: ReviewRubric
    org_standard_categories: list[str]

    def __init__(
        self,
        name: str,
        domain: ReviewDomain,
        org_standard_categories: list[str],
        skills: list[BaseSkill],
        rubric: ReviewRubric | None = None,
    ):
        super().__init__(name=name, skills=skills)
        self.domain = domain
        self.org_standard_categories = org_standard_categories
        self.rubric = rubric or load_rubric(domain)

    def run(self, state: ProjectContext) -> ProjectContext:
        logger.info(
            "Reviewer '%s' (%s) starting review across %d dimension(s)",
            self.name,
            self.domain.value,
            len(self.rubric.dimensions),
        )
        evaluate_dimension = self.get_skill(EVALUATE_DIMENSION_SKILL)
        org_standard = self._extract_org_standards(state)

        dimension_scores: list[DimensionScore] = []
        findings: list[Finding] = []
        skipped_dimensions: list[str] = []

        for dimension in self.rubric.dimensions:
            inputs = {
                "dimension_name": dimension.name,
                "dimension_description": dimension.description,
                "project_context": state,
                "org_standard": org_standard,
            }
            result = self.invoke_skill(
                evaluate_dimension,
                inputs,
                state,
                component_name=f"{self.domain.value}:{dimension.name}",
            )
            if result is None:
                logger.warning(
                    "Reviewer '%s' skipping dimension '%s' after skill failure",
                    self.name,
                    dimension.name,
                )
                skipped_dimensions.append(dimension.name)
                continue

            score, dimension_findings = self._parse_dimension_result(result)
            dimension_scores.append(score)
            findings.extend(dimension_findings)

        domain_score = self._aggregate_score(dimension_scores)
        summary = self._build_summary(dimension_scores, skipped_dimensions)

        review_result = ReviewResult(
            domain=self.domain,
            score=domain_score,
            dimension_scores=dimension_scores,
            findings=findings,
            summary=summary,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )
        state.reviews.append(review_result)
        logger.info(
            "Reviewer '%s' finished with score %d (%d/%d dimensions completed)",
            self.name,
            domain_score,
            len(dimension_scores),
            len(self.rubric.dimensions),
        )
        return state

    # ------------------------------------------------------------------

    def _extract_org_standards(self, state: ProjectContext) -> str | None:
        """Assemble the routed org standard content for this domain
        (ARCHITECTURE_v2.0.md section 5.2 org standard routing table). Every
        reviewer also receives organization_practices if it was provided."""
        categories = list(self.org_standard_categories)
        if "organization_practices" not in categories and state.org_standards.organization_practices:
            categories.append("organization_practices")

        sections = []
        for category in categories:
            content = getattr(state.org_standards, category, None)
            if content:
                sections.append(f"## {category}\n{content}")

        if not sections:
            logger.info(
                "Reviewer '%s' found no org standards for categories %s; "
                "evaluating against general best practices",
                self.name,
                categories,
            )
            return None
        return "\n\n".join(sections)

    @staticmethod
    def _parse_dimension_result(result: dict) -> tuple[DimensionScore, list[Finding]]:
        """The evaluate-dimension skill always returns a dimension score; it may
        also surface findings specific to that dimension. Both a flat
        ``DimensionScore``-shaped result and a ``{"dimension_score": ..., "findings":
        [...]}`` wrapper are accepted."""
        if "dimension_score" in result:
            score = DimensionScore.model_validate(result["dimension_score"])
        else:
            score = DimensionScore.model_validate(result)
        findings = [Finding.model_validate(f) for f in result.get("findings", [])]
        return score, findings

    @staticmethod
    def _aggregate_score(dimension_scores: list[DimensionScore]) -> int:
        if not dimension_scores:
            logger.error("All rubric dimensions failed to evaluate; defaulting domain score to 1")
            return 1
        return round(sum(d.score for d in dimension_scores) / len(dimension_scores))

    def _build_summary(
        self, dimension_scores: list[DimensionScore], skipped_dimensions: list[str]
    ) -> str:
        total = len(dimension_scores) + len(skipped_dimensions)
        summary = f"Evaluated {len(dimension_scores)}/{total} rubric dimensions for {self.domain.value}."
        if skipped_dimensions:
            summary += f" Skipped due to skill failure: {', '.join(skipped_dimensions)}."
        return summary
