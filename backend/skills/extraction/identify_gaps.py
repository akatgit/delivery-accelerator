"""identify-gaps skill (ARCHITECTURE_v2.0.md sections 5.1, 6.1; FR-1.8).

Identifies gaps and ambiguities across the full ProjectContext extracted so
far. Per ARCHITECTURE_v2.0.md section 6.1, this skill's input is already
structured (not a raw document), so it is not expected to need chunking in
practice -- BaseSkill's default `max_input_tokens` is left in place as a
safety net rather than disabled outright.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component, Gap, NFR, ProjectContext, Story, TechStackItem
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/extraction/identify_gaps.md"


class GapExtraction(BaseModel):
    """Wraps `list[Gap]` in an object field for Anthropic's tool-use schema
    (see `TechStackExtraction` in `extract_tech_stack.py` for why)."""

    items: list[Gap] = Field(default_factory=list)


def _format_tech_stack(tech_stack: list[TechStackItem]) -> str:
    if not tech_stack:
        return "(none extracted yet)"
    lines = []
    for item in tech_stack:
        version = f" {item.version}" if item.version else ""
        lines.append(f"- [{item.category}] {item.technology}{version}")
    return "\n".join(lines)


def _format_components(components: list[Component]) -> str:
    if not components:
        return "(none extracted yet)"
    return "\n".join(f"- {c.name} ({c.type}): {c.description}" for c in components)


def _format_nfrs(nfrs: list[NFR]) -> str:
    if not nfrs:
        return "(none extracted yet)"
    return "\n".join(f"- [{n.category}] {n.requirement}" for n in nfrs)


def _format_stories(stories: list[Story]) -> str:
    if not stories:
        return "(none extracted yet)"
    return "\n".join(
        f"- {s.id}: {s.title} ({len(s.acceptance_criteria)} acceptance criteria)" for s in stories
    )


class IdentifyGapsSkill(BaseSkill):
    """Identifies gaps and ambiguities across the full ProjectContext (FR-1.8)."""

    name = "identify-gaps"
    description = "Identifies gaps and ambiguities across everything extracted so far."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GapExtraction
    use_structured_output = True

    @staticmethod
    def build_inputs(project_context: ProjectContext) -> dict:
        """Assemble this skill's input from the full ProjectContext."""
        return {
            "project_name": project_context.project_name,
            "project_description": project_context.project_description,
            "source_documents": ", ".join(project_context.source_documents) or "(none)",
            "tech_stack_context": _format_tech_stack(project_context.tech_stack),
            "components_context": _format_components(project_context.components),
            "nfrs_context": _format_nfrs(project_context.nfrs),
            "stories_context": _format_stories(project_context.stories),
        }
