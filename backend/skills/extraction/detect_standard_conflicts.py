"""detect-standard-conflicts skill (ARCHITECTURE_v2.0.md section 4.4;
BRD_v2.0.md section 14.3, FR-1.5).

Scans all uploaded org standards for contradictory rules before the pipeline
starts. Standards are small (ARCHITECTURE_v2.0.md section 6.1: "No, standards
are small"), so this skill never needs BaseSkill's map-reduce chunking in
practice.
"""

from __future__ import annotations

from pydantic import RootModel

from backend.schemas.project_context import OrgStandards, StandardConflict
from backend.skills.base import BaseSkill
from backend.tools.standards_loader import ALL_CATEGORIES, route_standards

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/extraction/detect_standard_conflicts.md"


class StandardConflictList(RootModel[list[StandardConflict]]):
    """The ``list[StandardConflict]`` output of the detect-standard-conflicts skill."""


class DetectStandardConflictsSkill(BaseSkill):
    """Analyzes all org standard contents for contradictory rules (FR-1.5)."""

    name = "detect-standard-conflicts"
    description = "Detects contradictions between uploaded org engineering standards."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = StandardConflictList

    @staticmethod
    def build_inputs(org_standards: OrgStandards) -> dict:
        """Assemble this skill's input: all org standard contents, concatenated
        with category headers, across every recognized category."""
        return {"org_standards_content": route_standards(org_standards, list(ALL_CATEGORIES))}
