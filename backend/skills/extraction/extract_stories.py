"""extract-stories skill (ARCHITECTURE_v2.0.md sections 5.1, 6.1; FR-1.7).

Extracts user stories from the stories document, using the already-extracted
components as context. Large stories documents trigger BaseSkill's map-reduce
chunking (default `max_input_tokens`/`chunk_merge_strategy`, unlike
extract-tech-stack and extract-components, which override them explicitly).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component, Story
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/extraction/extract_stories.md"


class StoryExtraction(BaseModel):
    """Wraps `list[Story]` in an object field for Anthropic's tool-use schema
    (see `TechStackExtraction` in `extract_tech_stack.py` for why)."""

    items: list[Story] = Field(default_factory=list)


def _format_components(components: list[Component]) -> str:
    if not components:
        return "(none extracted yet)"
    return "\n".join(f"- {c.name} ({c.type}): {c.description}" for c in components)


class ExtractStoriesSkill(BaseSkill):
    """Extracts user stories from the stories document, with components
    context (FR-1.7)."""

    name = "extract-stories"
    description = "Extracts user stories from the stories document."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = StoryExtraction
    use_structured_output = True

    @staticmethod
    def build_inputs(stories_doc: str, components: list[Component]) -> dict:
        """Assemble this skill's input. `stories_doc` is the field expected to
        grow large enough to trigger chunking."""
        return {
            "stories_doc": stories_doc,
            "components_context": _format_components(components),
        }
