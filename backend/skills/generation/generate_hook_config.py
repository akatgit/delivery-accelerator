"""generate-hook-config skill (ARCHITECTURE_v2.0.md section 5.7; BRD_v2.0.md
FR-4.8).

Generates one hook configuration (pre-commit validation, PR templates, lint
rules, formatting rules, architecture validation, security checks,
dependency validation). Hook rules must enforce what instructions.md and org
standards define (FR-4.8.3), so instructions.md conventions and the
standards most relevant to hooks (cicd, coding, repository_conventions) are
required inputs.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.project_context import OrgStandards
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/generation/generate_hook_config.md"


class GeneratedHookConfig(BaseModel):
    """The generated content for one hook configuration."""

    content: str


def _standard_or_missing(org_standards: OrgStandards, category: str) -> str:
    content = getattr(org_standards, category, None)
    return content if content else f"(no {category} standard provided; use general best practices)"


class GenerateHookConfigSkill(BaseSkill):
    """Generates one hook configuration for a given hook type (FR-4.8.2)."""

    name = "generate-hook-config"
    description = "Generates a hook configuration for a given hook type."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedHookConfig
    use_structured_output = True

    @staticmethod
    def build_inputs(hook_type: str, org_standards: OrgStandards, instructions_md_conventions: str) -> dict:
        return {
            "hook_type": hook_type,
            "cicd_standard": _standard_or_missing(org_standards, "cicd"),
            "coding_standard": _standard_or_missing(org_standards, "coding"),
            "repository_conventions_standard": _standard_or_missing(org_standards, "repository_conventions"),
            "instructions_md_conventions": instructions_md_conventions,
        }
