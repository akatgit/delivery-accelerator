"""detect-contradictions skill (ARCHITECTURE_v2.0.md section 5.4; FR-2.10.3).

Identifies cases where two reviewers make opposing recommendations for the
same concern (e.g. security says "add auth at gateway" while architecture
says "keep gateway stateless"). Flagged for human resolution -- this skill
(and ReviewQAAgent) never picks a winner.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.review import Finding
from backend.schemas.review_qa import Contradiction
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/qa/detect_contradictions.md"


class ContradictionList(BaseModel):
    """Wraps `list[Contradiction]` in an object field for Anthropic's tool-use
    schema (see the extraction skills for why)."""

    items: list[Contradiction] = Field(default_factory=list)


def _format_findings(tagged_findings: list[tuple[str, Finding]]) -> str:
    if not tagged_findings:
        return "(no findings)"
    lines = []
    for domain, finding in tagged_findings:
        lines.append(
            f"- id={finding.id} [{domain}] severity={finding.severity.value}: {finding.title}\n"
            f"  recommendation: {finding.recommendation}"
        )
    return "\n".join(lines)


class DetectContradictionsSkill(BaseSkill):
    """Identifies opposing recommendations between reviewers (FR-2.10.3)."""

    name = "detect-contradictions"
    description = "Identifies cases where two reviewers recommend opposing approaches."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = ContradictionList
    use_structured_output = True

    @staticmethod
    def build_inputs(tagged_findings: list[tuple[str, Finding]]) -> dict:
        """`tagged_findings` is a list of (domain, Finding) pairs across all
        completed reviews."""
        return {"all_findings": _format_findings(tagged_findings)}
