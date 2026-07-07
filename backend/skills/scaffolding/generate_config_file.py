"""generate-config-file skill (ARCHITECTURE_v2.0.md section 5.9, 6.5;
BRD_v2.0.md FR-5.2).

Generates one boilerplate configuration file (Docker, environment config,
CI/CD pipeline definition), tuned to the project's tech stack and, where
relevant, the org's CI/CD standard.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.project_context import OrgStandards, TechStackItem
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/scaffolding/generate_config_file.md"


class GeneratedConfigFile(BaseModel):
    """The generated content for one boilerplate configuration file."""

    content: str


def _format_tech_stack(tech_stack: list[TechStackItem]) -> str:
    if not tech_stack:
        return "(none extracted)"
    lines = []
    for item in tech_stack:
        version = f" {item.version}" if item.version else ""
        lines.append(f"- [{item.category}] {item.technology}{version}")
    return "\n".join(lines)


class GenerateConfigFileSkill(BaseSkill):
    """Generates one boilerplate config file for a given config type (FR-5.2)."""

    name = "generate-config-file"
    description = "Generates a boilerplate configuration file for a given config type."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedConfigFile
    use_structured_output = True

    @staticmethod
    def build_inputs(config_type: str, org_standards: OrgStandards, tech_stack: list[TechStackItem]) -> dict:
        return {
            "config_type": config_type,
            "cicd_standard": org_standards.cicd or "(no cicd standard provided; use general best practices)",
            "tech_stack_context": _format_tech_stack(tech_stack),
        }
