"""generate-tool-config skill (ARCHITECTURE_v2.0.md section 5.7; BRD_v2.0.md
FR-4.10).

Generates one AI assistant configuration file (.cursorrules,
.github/copilot-instructions.md, Slingshot config) by filling in a
tool-specific structural template (backend/templates/tools/*.j2) with
guidance drawn from instructions.md and the project context (FR-4.10.2). All
three tool templates must produce equivalent guidance despite their
different formats/conventions (FR-4.10.3).

The `.j2` template is rendered by the caller (a future AI Development Setup
Agent) with cheap, deterministic variables (project_name, project_description)
before being passed here as `tool_template` -- this skill only fills the
tool-specific placeholders that require real judgment (architecture,
coding/security/testing guidance, etc.), not the mechanical substitution.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/generate_tool_config.md"


class GeneratedToolConfig(BaseModel):
    """The generated content for one tool-specific AI assistant config file."""

    content: str


class GenerateToolConfigSkill(BaseSkill):
    """Fills a tool-specific config template with project-specific guidance
    from instructions.md (FR-4.10.1, FR-4.10.2)."""

    name = "generate-tool-config"
    description = "Fills a tool-specific config template with guidance from instructions.md."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedToolConfig
    use_structured_output = True

    @staticmethod
    def build_inputs(
        tool_name: str,
        tool_template: str,
        instructions_md_content: str,
        project_context_summary: str,
    ) -> dict:
        return {
            "tool_name": tool_name,
            "tool_template": tool_template,
            "instructions_md_content": instructions_md_content,
            "project_context_summary": project_context_summary,
        }
