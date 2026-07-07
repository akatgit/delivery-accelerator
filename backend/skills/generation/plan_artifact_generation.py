"""plan-artifact-generation skill (ARCHITECTURE_v2.0.md section 5.6; FR-4.1
through FR-4.3).

Plans which AI development artifacts to generate, which org standard (if
any) feeds each, and which fall back to LLM defaults. Only ACCEPTED findings
may inform the plan (FR-4.2); overridden findings and the unchosen side of a
resolved contradiction are excluded by the caller (ContextSynthesizerAgent)
before this skill ever sees them -- the prompt also explicitly instructs the
model never to let excluded findings influence the plan, as a second layer of
defense on top of that deterministic filtering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.artifacts import PatternDefinition
from backend.schemas.project_context import OrgStandards
from backend.schemas.review import Finding
from backend.skills.base import BaseSkill
from backend.tools.standards_loader import ALL_CATEGORIES

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/plan_artifact_generation.md"


class ArtifactPlanEntry(BaseModel):
    """One planned artifact section within the generation plan."""

    artifact_type: str = Field(description='e.g. "instructions_section:security", "skill_file:repository-pattern".')
    source_standard_category: str | None = Field(
        default=None, description="The org standard category governing this artifact, if any."
    )
    used_default: bool = Field(
        description="True if this section will be generated from LLM best practices, not an uploaded standard (FR-4.3)."
    )
    contributing_findings: list[str] = Field(default_factory=list)
    notes: str = ""


class ArtifactGenerationPlan(BaseModel):
    """The full generation plan (FR-4.1 through FR-4.3). Already a proper
    object schema (not a bare list), so no "items" wrapper is needed for
    Anthropic's tool-use schema."""

    entries: list[ArtifactPlanEntry] = Field(default_factory=list)
    excluded_recommendations: list[str] = Field(
        default_factory=list,
        description="Finding IDs excluded from planning (overridden, or the unchosen side of a resolved contradiction).",
    )
    summary: str = ""


def _format_patterns(patterns: list[PatternDefinition]) -> str:
    if not patterns:
        return "(none identified)"
    return "\n".join(f"- {pattern.name}: {pattern.description}" for pattern in patterns)


def _format_org_standards_presence(org_standards: OrgStandards) -> str:
    lines = []
    for category in ALL_CATEGORIES:
        present = bool(getattr(org_standards, category, None))
        lines.append(f"- {category}: {'provided' if present else 'MISSING (will use LLM best practices/default)'}")
    return "\n".join(lines)


def _format_findings(tagged_findings: list[tuple[str, Finding]]) -> str:
    if not tagged_findings:
        return "(none)"
    return "\n".join(
        f"- id={finding.id} [{domain}]: {finding.title} -- {finding.recommendation}"
        for domain, finding in tagged_findings
    )


class PlanArtifactGenerationSkill(BaseSkill):
    """Plans the AI development artifacts to generate (FR-4.1 through FR-4.3)."""

    name = "plan-artifact-generation"
    description = "Plans which artifacts to generate, which standard feeds each, and which use defaults."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = ArtifactGenerationPlan
    use_structured_output = True

    @staticmethod
    def build_inputs(
        patterns: list[PatternDefinition],
        org_standards: OrgStandards,
        accepted_findings: list[tuple[str, Finding]],
        excluded_findings: list[tuple[str, Finding]],
    ) -> dict:
        """`accepted_findings` and `excluded_findings` must already be
        partitioned by the caller (ContextSynthesizerAgent) using each
        finding's status: ACCEPTED goes in the former, OVERRIDDEN/RESOLVED in
        the latter (FR-4.2)."""
        return {
            "patterns_context": _format_patterns(patterns),
            "org_standards_context": _format_org_standards_presence(org_standards),
            "accepted_findings_context": _format_findings(accepted_findings),
            "excluded_findings_context": _format_findings(excluded_findings),
        }
