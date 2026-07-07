"""generate-folder-structure skill (ARCHITECTURE_v2.0.md section 5.9, 6.5;
BRD_v2.0.md FR-5.1).

Generates the project's folder structure aligned with its component design.
If an existing codebase was provided, the structure integrates with it
rather than replacing it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component, ExistingCodebase, TechStackItem
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/scaffolding/generate_folder_structure.md"


class GeneratedFolderStructure(BaseModel):
    """The generated directory tree, as a nested dict (folders map to nested
    dicts of their contents; files map to the literal string "file")."""

    tree: dict = Field(default_factory=dict)


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


def _format_existing_codebase(existing_codebase: ExistingCodebase | None) -> str:
    if existing_codebase is None:
        return "(none provided -- greenfield project)"
    lines = [f"Source: {existing_codebase.source}", f"Notes: {existing_codebase.notes}"]
    if existing_codebase.folder_structure:
        lines.append(f"Existing folder structure: {existing_codebase.folder_structure}")
    return "\n".join(lines)


class GenerateFolderStructureSkill(BaseSkill):
    """Generates the project folder structure (FR-5.1)."""

    name = "generate-folder-structure"
    description = "Generates the project folder structure aligned with component design."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedFolderStructure
    use_structured_output = True

    @staticmethod
    def build_inputs(
        components: list[Component],
        tech_stack: list[TechStackItem],
        existing_codebase: ExistingCodebase | None,
    ) -> dict:
        return {
            "tech_stack_context": _format_tech_stack(tech_stack),
            "components_context": _format_components(components),
            "existing_codebase_context": _format_existing_codebase(existing_codebase),
        }
