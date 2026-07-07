"""extract-tech-stack skill (ARCHITECTURE_v2.0.md sections 5.1, 6.1; FR-1.7).

Extracts the declared technology stack from tech preferences and the
architecture document. Large architecture docs trigger BaseSkill's map-reduce
chunking; results are merged and deduplicated since the same technology (e.g.
"PostgreSQL") may legitimately be mentioned in more than one chunk.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.project_context import TechStackItem
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/extraction/extract_tech_stack.md"


class TechStackExtraction(BaseModel):
    """Wraps `list[TechStackItem]` in an object field. Anthropic's tool-use
    schema (used by `with_structured_output`) requires a top-level object, not
    a bare array, so list-producing skills wrap their list under `items`."""

    items: list[TechStackItem] = Field(default_factory=list)


class ExtractTechStackSkill(BaseSkill):
    """Extracts the technology stack from tech preferences + architecture doc
    content (FR-1.7)."""

    name = "extract-tech-stack"
    description = "Extracts the declared technology stack from project documents."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = TechStackExtraction
    max_input_tokens = 6000
    chunk_merge_strategy = "merge_and_deduplicate"
    use_structured_output = True

    @staticmethod
    def build_inputs(tech_preferences: str, architecture_doc: str) -> dict:
        """Assemble this skill's input. `architecture_doc` is the field
        expected to grow large enough to trigger chunking; `tech_preferences`
        is held constant across chunks."""
        return {
            "tech_preferences": tech_preferences or "(none provided)",
            "architecture_doc": architecture_doc,
        }
