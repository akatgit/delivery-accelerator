"""identify-patterns skill (ARCHITECTURE_v2.0.md section 5.6).

Determines which architectural/implementation patterns this project needs.
Only ACCEPTED findings inform this (FR-4.2) -- overridden findings and the
unchosen side of a resolved contradiction are filtered out by the caller
(ContextSynthesizerAgent) before this skill ever sees them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component, NFR, ProjectContext, TechStackItem
from backend.schemas.review import Finding
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/identify_patterns.md"


class IdentifiedPattern(BaseModel):
    """A pattern identified as needed, before it has a template/skill
    assigned for actual generation (that happens deterministically in
    ContextSynthesizerAgent, since deriving a template path is not an LLM
    judgment call)."""

    name: str
    description: str
    applicable_components: list[str] = Field(default_factory=list)


class IdentifiedPatternList(BaseModel):
    """Wraps `list[IdentifiedPattern]` in an object field for Anthropic's
    tool-use schema (see the extraction skills for why)."""

    items: list[IdentifiedPattern] = Field(default_factory=list)


def _format_tech_stack(tech_stack: list[TechStackItem]) -> str:
    if not tech_stack:
        return "(none extracted)"
    lines = []
    for item in tech_stack:
        version = f" {item.version}" if item.version else ""
        lines.append(f"- [{item.category}] {item.technology}{version}")
    return "\n".join(lines)


def _format_components(components: list[Component]) -> str:
    if not components:
        return "(none extracted)"
    lines = []
    for component in components:
        lines.append(f"- {component.name} ({component.type}): {component.description}")
        if component.dependencies:
            lines.append(f"  dependencies: {', '.join(component.dependencies)}")
    return "\n".join(lines)


def _format_nfrs(nfrs: list[NFR]) -> str:
    if not nfrs:
        return "(none extracted)"
    return "\n".join(f"- [{nfr.category}] {nfr.requirement}" for nfr in nfrs)


def _format_findings(tagged_findings: list[tuple[str, Finding]]) -> str:
    if not tagged_findings:
        return "(none)"
    return "\n".join(
        f"- id={finding.id} [{domain}]: {finding.title} -- {finding.recommendation}"
        for domain, finding in tagged_findings
    )


class IdentifyPatternsSkill(BaseSkill):
    """Identifies the architectural/implementation patterns this project needs."""

    name = "identify-patterns"
    description = "Determines which architectural/implementation patterns this project needs."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = IdentifiedPatternList
    use_structured_output = True

    @staticmethod
    def build_inputs(
        project_context: ProjectContext, accepted_findings: list[tuple[str, Finding]]
    ) -> dict:
        """`accepted_findings` must already be filtered to only
        `FindingStatus.ACCEPTED` entries (FR-4.2) by the caller."""
        return {
            "tech_stack_context": _format_tech_stack(project_context.tech_stack),
            "components_context": _format_components(project_context.components),
            "nfrs_context": _format_nfrs(project_context.nfrs),
            "accepted_findings_context": _format_findings(accepted_findings),
        }
