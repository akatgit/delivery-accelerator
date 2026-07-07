"""extract-nfrs skill (ARCHITECTURE_v2.0.md sections 5.1, 6.1; FR-1.7).

Extracts non-functional requirements from the BRD, using the already-extracted
components as context. Large BRDs trigger BaseSkill's map-reduce chunking
(default `max_input_tokens`/`chunk_merge_strategy`, unlike extract-tech-stack
and extract-components, which override them explicitly).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import Component, NFR
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/extraction/extract_nfrs.md"


class NFRExtraction(BaseModel):
    """Wraps `list[NFR]` in an object field for Anthropic's tool-use schema
    (see `TechStackExtraction` in `extract_tech_stack.py` for why)."""

    items: list[NFR] = Field(default_factory=list)


def _format_components(components: list[Component]) -> str:
    if not components:
        return "(none extracted yet)"
    return "\n".join(f"- {c.name} ({c.type}): {c.description}" for c in components)


class ExtractNFRsSkill(BaseSkill):
    """Extracts non-functional requirements from the BRD, with components
    context (FR-1.7)."""

    name = "extract-nfrs"
    description = "Extracts non-functional requirements from the BRD."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = NFRExtraction
    use_structured_output = True

    @staticmethod
    def build_inputs(brd_content: str, components: list[Component]) -> dict:
        """Assemble this skill's input. `brd_content` is the field expected to
        grow large enough to trigger chunking."""
        return {
            "brd_content": brd_content,
            "components_context": _format_components(components),
        }
