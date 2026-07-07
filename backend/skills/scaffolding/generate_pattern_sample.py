"""generate-pattern-sample skill (ARCHITECTURE_v2.0.md section 5.9, 6.5;
BRD_v2.0.md FR-5.3).

Generates a sample implementation, test file, and usage header for one
identified pattern.
"""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.artifacts import PatternDefinition
from backend.schemas.project_context import OrgStandards
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/scaffolding/generate_pattern_sample.md"


class GeneratedPatternSample(BaseModel):
    """The generated implementation, test file, and usage header for one
    pattern (FR-5.3)."""

    implementation: str
    test_file: str
    usage_header: str


class GeneratePatternSampleSkill(BaseSkill):
    """Generates a sample implementation, test file, and usage header for a
    pattern (FR-5.3)."""

    name = "generate-pattern-sample"
    description = "Generates a sample implementation, test file, and usage header for a pattern."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = GeneratedPatternSample
    use_structured_output = True

    @staticmethod
    def build_inputs(
        pattern: PatternDefinition,
        org_standards: OrgStandards,
        instructions_md_conventions: str,
    ) -> dict:
        return {
            "pattern_name": pattern.name,
            "pattern_description": pattern.description,
            "applicable_components": ", ".join(pattern.applicable_components) or "(none listed)",
            "coding_standard": org_standards.coding or "(no coding standard provided; use general best practices)",
            "testing_standard": org_standards.testing or "(no testing standard provided; use general best practices)",
            "instructions_md_conventions": instructions_md_conventions,
        }
