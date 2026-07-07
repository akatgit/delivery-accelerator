"""generate-prompt-entry skill (ARCHITECTURE_v2.0.md section 5.7; BRD_v2.0.md
FR-4.9).

Generates one project-specific prompt library entry (service generation, API
implementation, database access, event publishing, testing, refactoring,
code review), tuned to the project's tech stack and instructions.md
conventions (FR-4.9.2).
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.project_context import TechStackItem
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/generate_prompt_entry.md"


class GeneratedPromptEntry(BaseModel):
    """The generated content for one prompt library entry."""

    content: str


def _format_tech_stack(tech_stack: list[TechStackItem]) -> str:
    if not tech_stack:
        return "(none extracted)"
    lines = []
    for item in tech_stack:
        version = f" {item.version}" if item.version else ""
        lines.append(f"- [{item.category}] {item.technology}{version}")
    return "\n".join(lines)


class GeneratePromptEntrySkill(BaseSkill):
    """Generates one prompt library entry for a given category (FR-4.9.1)."""

    name = "generate-prompt-entry"
    description = "Generates a project-specific prompt library entry for a given category."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedPromptEntry
    use_structured_output = True

    @staticmethod
    def build_inputs(category: str, tech_stack: list[TechStackItem], instructions_md_conventions: str) -> dict:
        return {
            "category": category,
            "tech_stack_context": _format_tech_stack(tech_stack),
            "instructions_md_conventions": instructions_md_conventions,
        }
