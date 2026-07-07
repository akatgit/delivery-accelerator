"""generate-instruction-section skill (ARCHITECTURE_v2.0.md section 5.7;
BRD_v2.0.md FR-4.6).

Generates one section of instructions.md. Where an org standard is provided
for this section's category, the section follows it precisely (FR-4.3);
where missing, the section is generated from LLM best practices and marked
with a visible default warning. Only accepted findings may inform the
section (FR-4.2) -- contradiction resolutions are already reflected in
`accepted_findings` by the time this skill runs, since the unchosen
alternative never reaches ACCEPTED status (see ContextSynthesizerAgent).
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.project_context import Component, TechStackItem
from backend.schemas.review import Finding
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/generate_instruction_section.md"


class GeneratedInstructionSection(BaseModel):
    """The generated markdown content for one instructions.md section."""

    content: str


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
    return "\n".join(f"- {component.name} ({component.type}): {component.description}" for component in components)


def _format_findings(tagged_findings: list[tuple[str, Finding]]) -> str:
    if not tagged_findings:
        return "(none)"
    return "\n".join(
        f"- id={finding.id} [{domain}] {finding.severity.value}: {finding.title} -- {finding.recommendation}"
        for domain, finding in tagged_findings
    )


class GenerateInstructionSectionSkill(BaseSkill):
    """Generates one section of instructions.md (FR-4.6.2)."""

    name = "generate-instruction-section"
    description = "Generates one instructions.md section for a given category."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedInstructionSection
    use_structured_output = True

    @staticmethod
    def build_inputs(
        category: str,
        org_standard_content: str | None,
        accepted_findings: list[tuple[str, Finding]],
        tech_stack: list[TechStackItem],
        components: list[Component],
    ) -> dict:
        """`accepted_findings` must already be filtered to `FindingStatus.ACCEPTED`
        entries by the caller (FR-4.2)."""
        return {
            "category": category,
            "org_standard_content": org_standard_content,
            "accepted_findings_context": _format_findings(accepted_findings),
            "tech_stack_context": _format_tech_stack(tech_stack),
            "components_context": _format_components(components),
        }
