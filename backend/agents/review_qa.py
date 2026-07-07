"""ReviewQAAgent (ARCHITECTURE_v2.0.md section 5.4; BRD_v2.0.md FR-2.10).

Validates the quality and consistency of the aggregated review before it
reaches the human. Invokes four LLM skills for semantic analysis, then
applies deterministic logic on top: merging duplicate findings (preserving
the higher severity, citing both contributing domains), recording severity
normalizations, and computing a 1-10 quality score. Per FR-2.10.8, this agent
never overrides reviewer scores, adds new findings, or second-guesses domain
expertise -- it validates quality, not correctness.
"""

from __future__ import annotations

import logging

from backend.agents.base import BaseAgent
from backend.schemas.project_context import ProjectContext
from backend.schemas.review import Finding, Severity
from backend.schemas.review_qa import Contradiction, ReviewQAResult
from backend.skills.base import BaseSkill
from backend.skills.qa.check_coverage import CheckCoverageSkill, CoverageWarning
from backend.skills.qa.deduplicate_findings import DeduplicateFindingsSkill, DuplicatePair
from backend.skills.qa.detect_contradictions import DetectContradictionsSkill
from backend.skills.qa.validate_actionability import LowQualityFinding, ValidateActionabilitySkill

logger = logging.getLogger(__name__)

_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.MAJOR: 1,
    Severity.MINOR: 2,
    Severity.SUGGESTION: 3,
}


class ReviewQAAgent(BaseAgent):
    """Runs the four QA skills over the aggregated review and writes a
    `ReviewQAResult` to state."""

    def __init__(self, skills: list[BaseSkill] | None = None):
        super().__init__(
            name="review-qa",
            skills=skills
            or [
                DeduplicateFindingsSkill(),
                DetectContradictionsSkill(),
                ValidateActionabilitySkill(),
                CheckCoverageSkill(),
            ],
        )

    def run(self, state: ProjectContext) -> ProjectContext:
        tagged_findings = self._collect_findings(state)
        total_findings = len(tagged_findings)

        if not state.reviews:
            logger.warning("review-qa: no reviews to validate")
            state.review_qa = ReviewQAResult(
                quality_score=1,
                duplicates_found=0,
                contradictions=[],
                severity_normalizations=[],
                low_quality_findings=[],
                coverage_warnings=[],
                summary="No reviews completed; nothing to validate.",
            )
            return state

        duplicates = self._run_deduplication(state, tagged_findings)
        contradictions = self._run_contradiction_detection(state, tagged_findings)
        low_quality = self._run_actionability_validation(state, tagged_findings)
        coverage_warnings = self._run_coverage_check(state)

        severity_normalizations: list[dict] = []
        for pair in duplicates:
            self._merge_pair(state, pair, severity_normalizations)

        quality_score = self._compute_quality_score(
            total_findings, duplicates, contradictions, low_quality, coverage_warnings
        )

        state.review_qa = ReviewQAResult(
            quality_score=quality_score,
            duplicates_found=len(duplicates),
            contradictions=contradictions,
            severity_normalizations=severity_normalizations,
            low_quality_findings=[lq.finding_id for lq in low_quality],
            coverage_warnings=[f"{w.domain}: {w.warning}" for w in coverage_warnings],
            summary=self._build_summary(total_findings, duplicates, contradictions, low_quality, coverage_warnings),
        )
        logger.info(
            "review-qa: quality_score=%d, %d duplicate(s), %d contradiction(s), "
            "%d low-quality finding(s), %d coverage warning(s)",
            quality_score,
            len(duplicates),
            len(contradictions),
            len(low_quality),
            len(coverage_warnings),
        )
        return state

    # ------------------------------------------------------------------
    # Skill invocations (each degrades to "no signal" on failure, per FR-2.10.8
    # -- QA never blocks the pipeline)
    # ------------------------------------------------------------------

    def _collect_findings(self, state: ProjectContext) -> list[tuple[str, Finding]]:
        return [(review.domain.value, finding) for review in state.reviews for finding in review.findings]

    def _find_finding(self, state: ProjectContext, finding_id: str) -> Finding | None:
        for review in state.reviews:
            for finding in review.findings:
                if finding.id == finding_id:
                    return finding
        return None

    def _run_deduplication(
        self, state: ProjectContext, tagged_findings: list[tuple[str, Finding]]
    ) -> list[DuplicatePair]:
        if len(tagged_findings) < 2:
            return []
        skill = self.get_skill(DeduplicateFindingsSkill.name)
        inputs = DeduplicateFindingsSkill.build_inputs(tagged_findings)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return []
        return [DuplicatePair.model_validate(item) for item in result["items"]]

    def _run_contradiction_detection(
        self, state: ProjectContext, tagged_findings: list[tuple[str, Finding]]
    ) -> list[Contradiction]:
        if len(tagged_findings) < 2:
            return []
        skill = self.get_skill(DetectContradictionsSkill.name)
        inputs = DetectContradictionsSkill.build_inputs(tagged_findings)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return []
        return [Contradiction.model_validate(item) for item in result["items"]]

    def _run_actionability_validation(
        self, state: ProjectContext, tagged_findings: list[tuple[str, Finding]]
    ) -> list[LowQualityFinding]:
        if not tagged_findings:
            return []
        skill = self.get_skill(ValidateActionabilitySkill.name)
        component_names = [component.name for component in state.components]
        inputs = ValidateActionabilitySkill.build_inputs(tagged_findings, component_names)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return []
        return [LowQualityFinding.model_validate(item) for item in result["items"]]

    def _run_coverage_check(self, state: ProjectContext) -> list[CoverageWarning]:
        if not state.reviews:
            return []
        skill = self.get_skill(CheckCoverageSkill.name)
        inputs = CheckCoverageSkill.build_inputs(state.reviews, state.components)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return []
        return [CoverageWarning.model_validate(item) for item in result["items"]]

    # ------------------------------------------------------------------
    # Deterministic merge logic (FR-2.10.2, FR-2.10.4)
    # ------------------------------------------------------------------

    def _merge_pair(
        self, state: ProjectContext, pair: DuplicatePair, severity_normalizations: list[dict]
    ) -> None:
        """Merges a duplicate pair: the more severe finding is kept as
        primary, the other is marked `duplicate_of` it, and the primary's
        `contributing_domains` cites both domains. If severities differed,
        the primary's severity is escalated to the higher one and a
        normalization note is recorded (FR-2.10.4)."""
        finding_a = self._find_finding(state, pair.finding_id_a)
        finding_b = self._find_finding(state, pair.finding_id_b)
        if finding_a is None or finding_b is None:
            logger.warning(
                "review-qa: duplicate pair references unknown finding id(s) (%s, %s); skipping",
                pair.finding_id_a,
                pair.finding_id_b,
            )
            return

        if _SEVERITY_RANK[finding_b.severity] < _SEVERITY_RANK[finding_a.severity]:
            primary, secondary = finding_b, finding_a
            primary_domain, secondary_domain = pair.domain_b, pair.domain_a
        else:
            primary, secondary = finding_a, finding_b
            primary_domain, secondary_domain = pair.domain_a, pair.domain_b

        if primary.severity != secondary.severity:
            severity_normalizations.append(
                {
                    "finding_id": primary.id,
                    "previous_severity": secondary.severity.value,
                    "escalated_to": primary.severity.value,
                    "note": (
                        f"Escalated from {secondary.severity.value} to {primary.severity.value}: "
                        f"{secondary_domain} rated this issue {secondary.severity.value} while "
                        f"{primary_domain} rated it {primary.severity.value}; the higher severity "
                        "is preserved."
                    ),
                }
            )

        primary.contributing_domains = sorted(set(primary.contributing_domains) | {primary_domain, secondary_domain})
        secondary.duplicate_of = primary.id

    # ------------------------------------------------------------------
    # Quality score (FR-2.10.7)
    # ------------------------------------------------------------------

    def _compute_quality_score(
        self,
        total_findings: int,
        duplicates: list[DuplicatePair],
        contradictions: list[Contradiction],
        low_quality: list[LowQualityFinding],
        coverage_warnings: list[CoverageWarning],
    ) -> int:
        """Reflects deduplication ratio, contradiction count, actionability
        rate, and coverage completeness (FR-2.10.7). Starts at 10 and
        deducts for each factor; there's no single canonical formula in the
        BRD, so this is one reasonable, deterministic weighting of the four
        named factors, clamped to the 1-10 range."""
        score = 10.0
        if total_findings:
            dedup_ratio = len(duplicates) / total_findings
            actionability_rate = 1 - (len(low_quality) / total_findings)
            score -= dedup_ratio * 4
            score -= (1 - actionability_rate) * 4
        score -= min(len(contradictions), 3)
        score -= min(len(coverage_warnings), 3)
        return max(1, min(10, round(score)))

    def _build_summary(
        self,
        total_findings: int,
        duplicates: list[DuplicatePair],
        contradictions: list[Contradiction],
        low_quality: list[LowQualityFinding],
        coverage_warnings: list[CoverageWarning],
    ) -> str:
        return (
            f"Validated {total_findings} finding(s) across all domains. "
            f"{len(duplicates)} duplicate pair(s) merged. "
            f"{len(contradictions)} contradiction(s) flagged for human resolution. "
            f"{len(low_quality)} finding(s) flagged as low-quality. "
            f"{len(coverage_warnings)} coverage warning(s)."
        )
