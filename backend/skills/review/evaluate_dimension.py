"""evaluate-dimension skill (ARCHITECTURE_v2.0.md sections 5.2, 6.2, 7.1;
FR-2.2, FR-2.3).

Evaluates a single rubric dimension against the project context and, where
provided, a routed org standard. Context is pre-selected by the caller (a
concise project excerpt, not raw source documents), so this skill never needs
BaseSkill's map-reduce chunking (section 6.2: "No (context pre-selected)").

Output is exactly `DimensionScore` (dimension, score, justification) per the
architecture's skills catalog -- there's no dedicated field for
affected_components/recommendation/based_on the way `Finding` has, so the
prompt's RULES instead shape the *content* of the free-text `justification`:
it must name real components, keep any recommendation tech-stack-specific, and
close with an explicit statement of what the score is based on.
"""

from __future__ import annotations

from backend.schemas.project_context import ProjectContext
from backend.schemas.review import DimensionScore, RubricDimension, ScoringGuide
from backend.skills.base import BaseSkill

PROMPT_TEMPLATE_PATH = "backend/prompts/templates/review/evaluate_dimension.md"


def _format_scoring_anchors(scoring_guide: ScoringGuide) -> str:
    return (
        f"1-2: {scoring_guide.anchor_1_2}\n"
        f"3-4: {scoring_guide.anchor_3_4}\n"
        f"5-6: {scoring_guide.anchor_5_6}\n"
        f"7-8: {scoring_guide.anchor_7_8}\n"
        f"9-10: {scoring_guide.anchor_9_10}"
    )


def format_project_context_excerpt(project_context: ProjectContext) -> str:
    """Builds a concise, review-focused excerpt of the ProjectContext: identity,
    tech stack, components (with responsibilities/dependencies/API
    contracts/data entities), NFRs, and stories. Reused by reviewer agents to
    build this skill's `project_context_excerpt` input so every dimension
    evaluation sees exactly the "relevant sections", not raw source documents.
    """
    lines = [
        f"Project: {project_context.project_name}",
        f"Description: {project_context.project_description}",
        "",
        "TECH STACK:",
    ]
    if project_context.tech_stack:
        for item in project_context.tech_stack:
            version = f" {item.version}" if item.version else ""
            lines.append(f"- [{item.category}] {item.technology}{version}")
    else:
        lines.append("(none extracted)")

    lines.append("")
    lines.append("COMPONENTS:")
    if project_context.components:
        for component in project_context.components:
            lines.append(f"- {component.name} ({component.type}): {component.description}")
            if component.responsibilities:
                lines.append(f"  responsibilities: {', '.join(component.responsibilities)}")
            if component.dependencies:
                lines.append(f"  dependencies: {', '.join(component.dependencies)}")
            if component.api_contracts:
                lines.append(f"  api_contracts: {', '.join(component.api_contracts)}")
            if component.data_entities:
                lines.append(f"  data_entities: {', '.join(component.data_entities)}")
    else:
        lines.append("(none extracted)")

    lines.append("")
    lines.append("NON-FUNCTIONAL REQUIREMENTS:")
    if project_context.nfrs:
        for nfr in project_context.nfrs:
            lines.append(f"- [{nfr.category}] {nfr.requirement} (measurable={nfr.measurable})")
    else:
        lines.append("(none extracted)")

    lines.append("")
    lines.append("STORIES:")
    if project_context.stories:
        for story in project_context.stories:
            related = ", ".join(story.related_components) or "none"
            lines.append(f"- {story.id}: {story.title} (touches: {related})")
    else:
        lines.append("(none extracted)")

    return "\n".join(lines)


class EvaluateDimensionSkill(BaseSkill):
    """Evaluates a single rubric dimension of a software architecture
    (FR-2.2, FR-2.3)."""

    name = "evaluate-dimension"
    description = "Evaluates a single rubric dimension against project context and org standards."
    prompt_template_path = PROMPT_TEMPLATE_PATH
    output_schema = DimensionScore
    use_structured_output = True

    @staticmethod
    def build_inputs(
        dimension: RubricDimension,
        project_context_excerpt: str,
        org_standard_content: str | None,
    ) -> dict:
        """Assemble this skill's input from a rubric dimension (name,
        description, and scoring guide travel together) plus the caller's
        pre-built project context excerpt and routed org standard content."""
        return {
            "dimension_name": dimension.name,
            "dimension_description": dimension.description,
            "scoring_anchors": _format_scoring_anchors(dimension.scoring_guide),
            "project_context_excerpt": project_context_excerpt,
            "org_standard_content": org_standard_content,
        }
