"""generate-skill-file skill (ARCHITECTURE_v2.0.md section 5.7; BRD_v2.0.md
FR-4.7).

Generates one reusable AI skill file for a given architectural pattern. Each
generated skill inherits project-specific engineering standards from
instructions.md (FR-4.7.3), so instructions.md conventions are a required
input alongside the pattern and the org standards most relevant to writing
code (coding, testing, API design).
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.project_context import Component, OrgStandards
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/generate_skill_file.md"


class GeneratedSkillFile(BaseModel):
    """The generated content for one AI skill file."""

    content: str


def _format_components(components: list[Component]) -> str:
    if not components:
        return "(none extracted)"
    return "\n".join(f"- {component.name} ({component.type}): {component.description}" for component in components)


def _standard_or_missing(org_standards: OrgStandards, category: str) -> str:
    content = getattr(org_standards, category, None)
    return content if content else f"(no {category} standard provided; use general best practices)"


class GenerateSkillFileSkill(BaseSkill):
    """Generates one reusable AI skill file for an identified pattern (FR-4.7.2)."""

    name = "generate-skill-file"
    description = "Generates a reusable AI skill file for an identified pattern."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedSkillFile
    use_structured_output = True

    @staticmethod
    def build_inputs(
        pattern_name: str,
        components: list[Component],
        org_standards: OrgStandards,
        instructions_md_conventions: str,
    ) -> dict:
        return {
            "pattern_name": pattern_name,
            "components_context": _format_components(components),
            "coding_standard": _standard_or_missing(org_standards, "coding"),
            "testing_standard": _standard_or_missing(org_standards, "testing"),
            "api_design_standard": _standard_or_missing(org_standards, "api_design"),
            "instructions_md_conventions": instructions_md_conventions,
        }
