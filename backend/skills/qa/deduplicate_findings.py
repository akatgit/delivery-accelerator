"""deduplicate-findings skill (ARCHITECTURE_v2.0.md section 5.4; FR-2.10.2).

Semantic deduplication across all reviewer findings -- the LLM identifies
findings from different domains that describe the same underlying issue
(e.g. "missing rate limiting" from security and "no API throttling" from
performance), which string matching would miss entirely. The actual merge
(preserving the higher severity, citing both domains) is performed by
ReviewQAAgent; this skill only identifies pairs and explains why.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.review import Finding
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/qa/deduplicate_findings.md"


class DuplicatePair(BaseModel):
    """Two findings from different domains identified as describing the same
    underlying issue (FR-2.10.2)."""

    finding_id_a: str
    finding_id_b: str
    domain_a: str
    domain_b: str
    reason: str = Field(description="Why these two findings describe the same underlying issue.")
    merge_recommendation: str = Field(
        description="A short recommendation for how the merged finding should read."
    )


class DuplicatePairList(BaseModel):
    """Wraps `list[DuplicatePair]` in an object field for Anthropic's tool-use
    schema (see the extraction skills for why)."""

    items: list[DuplicatePair] = Field(default_factory=list)


def _format_findings(tagged_findings: list[tuple[str, Finding]]) -> str:
    if not tagged_findings:
        return "(no findings)"
    lines = []
    for domain, finding in tagged_findings:
        lines.append(
            f"- id={finding.id} [{domain}] severity={finding.severity.value}: {finding.title}\n"
            f"  description: {finding.description}\n"
            f"  recommendation: {finding.recommendation}"
        )
    return "\n".join(lines)


class DeduplicateFindingsSkill(BaseSkill):
    """Identifies semantically duplicate findings across domains (FR-2.10.2)."""

    name = "deduplicate-findings"
    description = "Identifies findings across domains that describe the same underlying issue."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = DuplicatePairList
    use_structured_output = True

    @staticmethod
    def build_inputs(tagged_findings: list[tuple[str, Finding]]) -> dict:
        """`tagged_findings` is a list of (domain, Finding) pairs across all
        completed reviews."""
        return {"all_findings": _format_findings(tagged_findings)}
