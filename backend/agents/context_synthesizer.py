"""ContextSynthesizerAgent (ARCHITECTURE_v2.0.md section 5.6).

Bridges review and generation: invokes identify-patterns and
plan-artifact-generation, then writes the results to state. Reads approved
context only -- per FR-4.2, overridden findings and the unchosen side of a
resolved contradiction (FR-3.6) must never influence what gets generated, so
this agent filters findings by status *before* either skill ever sees them,
and additionally strips any excluded finding ID that manages to slip into
the plan anyway (a deterministic guarantee on top of the prompt instruction,
not just best-effort LLM compliance).
"""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.schemas.artifacts import PatternDefinition
from backend.schemas.project_context import ProjectContext
from backend.schemas.review import Finding, FindingStatus
from backend.skills.base import BaseSkill
from backend.skills.generation.identify_patterns import IdentifiedPattern, IdentifyPatternsSkill
from backend.skills.generation.plan_artifact_generation import PlanArtifactGenerationSkill

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def _to_pattern_definition(identified: IdentifiedPattern) -> PatternDefinition:
    """Deriving a template path from a pattern name is a deterministic
    convention, not an LLM judgment call -- the skill only identifies which
    patterns are needed; this fills in where its sample will eventually live
    and which skill (section 6.5) will generate it."""
    slug = _slugify(identified.name)
    return PatternDefinition(
        name=identified.name,
        description=identified.description,
        applicable_components=identified.applicable_components,
        template_path=f"backend/templates/scaffolding/patterns/{slug}.py.j2",
        ai_skill_ref="generate-pattern-sample",
    )


class ContextSynthesizerAgent(BaseAgent):
    """Runs identify-patterns and plan-artifact-generation, writing
    `state.patterns` and `state.generation_plan`."""

    def __init__(self, skills: list[BaseSkill] | None = None):
        super().__init__(
            name="context-synthesizer",
            skills=skills or [IdentifyPatternsSkill(), PlanArtifactGenerationSkill()],
        )

    def run(self, state: ProjectContext) -> ProjectContext:
        accepted = self._findings_with_status(state, FindingStatus.ACCEPTED)
        excluded = self._findings_with_status(state, FindingStatus.OVERRIDDEN) + self._findings_with_status(
            state, FindingStatus.RESOLVED
        )

        patterns = self._run_identify_patterns(state, accepted)
        state.patterns = patterns

        plan = self._run_plan_artifact_generation(state, patterns, accepted, excluded)
        if plan is not None and hasattr(state, "generation_plan"):
            state.generation_plan = plan

        logger.info(
            "context-synthesizer: identified %d pattern(s), planned %d artifact(s) "
            "(%d accepted finding(s) considered, %d excluded)",
            len(patterns),
            len(plan["entries"]) if plan else 0,
            len(accepted),
            len(excluded),
        )
        return state

    # ------------------------------------------------------------------

    def _findings_with_status(self, state: ProjectContext, status: FindingStatus) -> list[tuple[str, Finding]]:
        return [
            (review.domain.value, finding)
            for review in state.reviews
            for finding in review.findings
            if finding.duplicate_of is None and finding.status == status
        ]

    def _run_identify_patterns(
        self, state: ProjectContext, accepted: list[tuple[str, Finding]]
    ) -> list[PatternDefinition]:
        skill = self.get_skill(IdentifyPatternsSkill.name)
        inputs = IdentifyPatternsSkill.build_inputs(state, accepted)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return []
        return [_to_pattern_definition(IdentifiedPattern.model_validate(item)) for item in result["items"]]

    def _run_plan_artifact_generation(
        self,
        state: ProjectContext,
        patterns: list[PatternDefinition],
        accepted: list[tuple[str, Finding]],
        excluded: list[tuple[str, Finding]],
    ) -> dict | None:
        skill = self.get_skill(PlanArtifactGenerationSkill.name)
        inputs = PlanArtifactGenerationSkill.build_inputs(patterns, state.org_standards, accepted, excluded)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return None

        excluded_ids = {finding.id for _, finding in excluded}
        for entry in result.get("entries", []):
            entry["contributing_findings"] = [
                finding_id for finding_id in entry.get("contributing_findings", []) if finding_id not in excluded_ids
            ]
        return result
