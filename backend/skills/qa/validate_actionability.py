"""validate-actionability skill (ARCHITECTURE_v2.0.md section 5.4; FR-2.10.5).

Checks whether each finding references real component names and gives a
tech-stack-specific recommendation, rather than generic filler advice.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.review import Finding
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/qa/validate_actionability.md"


class LowQualityFinding(BaseModel):
    """A finding flagged as low-quality by the actionability check (FR-2.10.5)."""

    finding_id: str
    reason: str = Field(description="Why this finding failed the actionability check.")


class LowQualityFindingList(BaseModel):
    """Wraps `list[LowQualityFinding]` in an object field for Anthropic's
    tool-use schema (see the extraction skills for why)."""

    items: list[LowQualityFinding] = Field(default_factory=list)


def _format_findings(tagged_findings: list[tuple[str, Finding]]) -> str:
    if not tagged_findings:
        return "(no findings)"
    lines = []
    for domain, finding in tagged_findings:
        components = ", ".join(finding.affected_components) or "(none listed)"
        lines.append(
            f"- id={finding.id} [{domain}]: {finding.title}\n"
            f"  affected_components: {components}\n"
            f"  recommendation: {finding.recommendation}"
        )
    return "\n".join(lines)


class ValidateActionabilitySkill(BaseSkill):
    """Validates that findings are actionable: real components, tech-stack-
    specific recommendations (FR-2.10.5)."""

    name = "validate-actionability"
    description = "Checks that findings reference real components and give specific recommendations."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = LowQualityFindingList
    use_structured_output = True

    @staticmethod
    def build_inputs(tagged_findings: list[tuple[str, Finding]], component_names: list[str]) -> dict:
        """`tagged_findings` is a list of (domain, Finding) pairs across all
        completed reviews; `component_names` are the real component names
        from `ProjectContext.components`."""
        return {
            "all_findings": _format_findings(tagged_findings),
            "valid_component_names": ", ".join(component_names) or "(none extracted)",
        }
