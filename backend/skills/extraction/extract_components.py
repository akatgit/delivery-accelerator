"""extract-components skill (ARCHITECTURE_v2.0.md sections 5.1, 6.1; FR-1.7).

Extracts architectural components from the architecture document, using the
already-extracted tech stack as context. Large architecture docs trigger
BaseSkill's map-reduce chunking; results are merged and deduplicated since the
same component may be described in more than one chunk.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component, TechStackItem
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/extraction/extract_components.md"


class ComponentExtraction(BaseModel):
    """Wraps `list[Component]` in an object field for Anthropic's tool-use
    schema (see `TechStackExtraction` in `extract_tech_stack.py` for why)."""

    items: list[Component] = Field(default_factory=list)


def _format_tech_stack(tech_stack: list[TechStackItem]) -> str:
    if not tech_stack:
        return "(none extracted yet)"
    lines = []
    for item in tech_stack:
        version = f" {item.version}" if item.version else ""
        lines.append(f"- [{item.category}] {item.technology}{version}")
    return "\n".join(lines)


class ExtractComponentsSkill(BaseSkill):
    """Extracts architectural components from the architecture doc, with tech
    stack context (FR-1.7)."""

    name = "extract-components"
    description = "Extracts architectural components from the architecture document."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = ComponentExtraction
    max_input_tokens = 6000
    chunk_merge_strategy = "merge_and_deduplicate"
    use_structured_output = True

    @staticmethod
    def build_inputs(architecture_doc: str, tech_stack: list[TechStackItem]) -> dict:
        """Assemble this skill's input. `architecture_doc` is the field
        expected to grow large enough to trigger chunking."""
        return {
            "architecture_doc": architecture_doc,
            "tech_stack_context": _format_tech_stack(tech_stack),
        }
