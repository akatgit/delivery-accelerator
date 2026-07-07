"""AIDevSetupAgent (ARCHITECTURE_v2.0.md section 5.7; BRD_v2.0.md FR-4).

Thin orchestrator generating every AI development artifact, in the order
section 5.7 requires: instructions.md sections first (assembled into one
document), since everything else references it -- skill files (one per
pattern), hook configs (one per hook type), prompt library entries (one per
category), then tool configs (one per AI tool), each passing the assembled
instructions.md as context.

Only ACCEPTED findings inform any artifact (FR-4.2): overridden findings and
the unchosen side of a resolved contradiction are filtered out before any
skill runs, so "the chosen approach is enforced, the unchosen excluded"
(section 5.7's contradiction handling) falls out of the same status filter
used by ContextSynthesizerAgent and the QA agent, rather than needing
special-cased logic here.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from jinja2 import Template

from backend.agents.base import BaseAgent
from backend.schemas.artifacts import AIArtifact
from backend.schemas.project_context import ProjectContext
from backend.schemas.review import Finding, FindingStatus
from backend.skills.base import BaseSkill
from backend.skills.generation.generate_hook_config import GenerateHookConfigSkill
from backend.skills.generation.generate_instruction_section import GenerateInstructionSectionSkill
from backend.skills.generation.generate_prompt_entry import GeneratePromptEntrySkill
from backend.skills.generation.generate_skill_file import GenerateSkillFileSkill
from backend.skills.generation.generate_tool_config import GenerateToolConfigSkill

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


# instructions.md sections (FR-4.6.1), mapped to the org standard category that
# governs each, where one exists. Not a 1:1 mapping -- FR-4.6.1 names 12
# instructions.md sections while FR-1.4 names 10 org standard categories.
# Sections with no direct standard (architecture principles, layer
# responsibilities, validation rules) always use LLM best practices.
INSTRUCTION_SECTIONS: list[tuple[str, str | None]] = [
    ("architecture principles", None),
    ("folder structure", "repository_conventions"),
    ("layer responsibilities", None),
    ("coding standards", "coding"),
    ("naming conventions", "naming"),
    ("API design conventions", "api_design"),
    ("logging standards", "logging"),
    ("exception handling strategy", "exception_handling"),
    ("validation rules", None),
    ("security guidelines", "security"),
    ("testing strategy", "testing"),
    ("documentation requirements", "organization_practices"),
]

HOOK_TYPES = [
    "pre-commit validation",
    "PR templates",
    "lint rules",
    "formatting rules",
    "architecture validation",
    "security checks",
    "dependency validation",
]  # FR-4.8.1

PROMPT_CATEGORIES = [
    "service generation",
    "API implementation",
    "database access",
    "event publishing",
    "testing",
    "refactoring",
    "code review",
]  # FR-4.9.1

TOOL_CONFIGS = [
    {"tool_name": "cursor", "template_file": "cursorrules.j2", "output_filename": ".cursorrules"},
    {
        "tool_name": "github-copilot",
        "template_file": "copilot-instructions.j2",
        "output_filename": ".github/copilot-instructions.md",
    },
    {"tool_name": "slingshot", "template_file": "slingshot-config.j2", "output_filename": "slingshot.config.yaml"},
]  # FR-4.10.1

TOOL_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "tools"


class AIDevSetupAgent(BaseAgent):
    """Generates instructions.md, skill files, hook configs, prompt library
    entries, and tool configs, in that order."""

    def __init__(self, skills: list[BaseSkill] | None = None):
        super().__init__(
            name="ai-dev-setup",
            skills=skills
            or [
                GenerateInstructionSectionSkill(),
                GenerateSkillFileSkill(),
                GenerateHookConfigSkill(),
                GeneratePromptEntrySkill(),
                GenerateToolConfigSkill(),
            ],
        )

    def run(self, state: ProjectContext) -> ProjectContext:
        accepted = self._accepted_findings(state)

        artifacts: list[AIArtifact] = []
        instructions_md = self._generate_instructions_md(state, accepted, artifacts)
        self._generate_skill_files(state, instructions_md, artifacts)
        self._generate_hook_configs(state, instructions_md, artifacts)
        self._generate_prompt_entries(state, instructions_md, artifacts)
        self._generate_tool_configs(state, instructions_md, artifacts)

        state.ai_artifacts = artifacts
        logger.info("ai-dev-setup: generated %d artifact(s)", len(artifacts))
        return state

    # ------------------------------------------------------------------

    def _accepted_findings(self, state: ProjectContext) -> list[tuple[str, Finding]]:
        """Only FindingStatus.ACCEPTED findings may inform any artifact
        (FR-4.2). This also excludes FindingStatus.RESOLVED -- the unchosen
        side of a human-resolved contradiction (FR-3.6) -- satisfying section
        5.7's contradiction handling without special-casing it here."""
        return [
            (review.domain.value, finding)
            for review in state.reviews
            for finding in review.findings
            if finding.duplicate_of is None and finding.status == FindingStatus.ACCEPTED
        ]

    # ------------------------------------------------------------------
    # Step 1: instructions.md -- must complete first (section 5.7)
    # ------------------------------------------------------------------

    def _generate_instructions_md(
        self,
        state: ProjectContext,
        accepted: list[tuple[str, Finding]],
        artifacts: list[AIArtifact],
    ) -> str:
        skill = self.get_skill(GenerateInstructionSectionSkill.name)
        sections: list[str] = []

        for category, standard_category in INSTRUCTION_SECTIONS:
            org_standard_content = (
                getattr(state.org_standards, standard_category, None) if standard_category else None
            )
            inputs = GenerateInstructionSectionSkill.build_inputs(
                category=category,
                org_standard_content=org_standard_content,
                accepted_findings=accepted,
                tech_stack=state.tech_stack,
                components=state.components,
            )
            result = self.invoke_skill(skill, inputs, state, component_name=f"instruction-section:{category}")
            if result is None:
                continue
            sections.append(result["content"])

            derived_from = [f"finding:{finding.id}" for _, finding in accepted]
            if standard_category and org_standard_content:
                derived_from.append(f"standard:{standard_category}")
            artifacts.append(
                AIArtifact(
                    type="instructions_section",
                    filename=f"instructions.md#{_slugify(category)}",
                    content=result["content"],
                    derived_from=derived_from,
                    used_default=org_standard_content is None,
                    prompt_version=skill.prompt_version,
                )
            )

        assembled = "# instructions.md\n\n" + "\n\n".join(sections)
        artifacts.append(
            AIArtifact(
                type="instructions_md",
                filename="instructions.md",
                content=assembled,
                derived_from=[f"finding:{finding.id}" for _, finding in accepted],
                used_default=any(standard is None for _, standard in INSTRUCTION_SECTIONS),
                prompt_version=skill.prompt_version,
            )
        )
        return assembled

    # ------------------------------------------------------------------
    # Step 2: skill files -- one per pattern, references instructions.md
    # ------------------------------------------------------------------

    def _generate_skill_files(self, state: ProjectContext, instructions_md: str, artifacts: list[AIArtifact]) -> None:
        skill = self.get_skill(GenerateSkillFileSkill.name)
        relevant_categories = ("coding", "testing", "api_design")

        for pattern in state.patterns:
            inputs = GenerateSkillFileSkill.build_inputs(
                pattern_name=pattern.name,
                components=state.components,
                org_standards=state.org_standards,
                instructions_md_conventions=instructions_md,
            )
            result = self.invoke_skill(skill, inputs, state, component_name=f"skill-file:{pattern.name}")
            if result is None:
                continue

            present = [c for c in relevant_categories if getattr(state.org_standards, c, None)]
            artifacts.append(
                AIArtifact(
                    type="skill_file",
                    filename=f"skills/{_slugify(pattern.name)}.md",
                    content=result["content"],
                    derived_from=["instructions.md", f"pattern:{pattern.name}"]
                    + [f"standard:{c}" for c in present],
                    used_default=not present,
                    prompt_version=skill.prompt_version,
                )
            )

    # ------------------------------------------------------------------
    # Step 3: hook configs -- one per hook type, references instructions.md
    # ------------------------------------------------------------------

    def _generate_hook_configs(self, state: ProjectContext, instructions_md: str, artifacts: list[AIArtifact]) -> None:
        skill = self.get_skill(GenerateHookConfigSkill.name)
        relevant_categories = ("cicd", "coding", "repository_conventions")

        for hook_type in HOOK_TYPES:
            inputs = GenerateHookConfigSkill.build_inputs(
                hook_type=hook_type,
                org_standards=state.org_standards,
                instructions_md_conventions=instructions_md,
            )
            result = self.invoke_skill(skill, inputs, state, component_name=f"hook-config:{hook_type}")
            if result is None:
                continue

            present = [c for c in relevant_categories if getattr(state.org_standards, c, None)]
            artifacts.append(
                AIArtifact(
                    type="hook_config",
                    filename=f"hooks/{_slugify(hook_type)}.md",
                    content=result["content"],
                    derived_from=["instructions.md"] + [f"standard:{c}" for c in present],
                    used_default=not present,
                    prompt_version=skill.prompt_version,
                )
            )

    # ------------------------------------------------------------------
    # Step 4: prompt library entries -- one per category
    # ------------------------------------------------------------------

    def _generate_prompt_entries(
        self, state: ProjectContext, instructions_md: str, artifacts: list[AIArtifact]
    ) -> None:
        skill = self.get_skill(GeneratePromptEntrySkill.name)

        for category in PROMPT_CATEGORIES:
            inputs = GeneratePromptEntrySkill.build_inputs(
                category=category,
                tech_stack=state.tech_stack,
                instructions_md_conventions=instructions_md,
            )
            result = self.invoke_skill(skill, inputs, state, component_name=f"prompt-entry:{category}")
            if result is None:
                continue

            artifacts.append(
                AIArtifact(
                    type="prompt_entry",
                    filename=f"prompts/{_slugify(category)}.md",
                    content=result["content"],
                    derived_from=["instructions.md"],
                    used_default=False,
                    prompt_version=skill.prompt_version,
                )
            )

    # ------------------------------------------------------------------
    # Step 5: tool configs -- one per AI tool, references instructions.md
    # ------------------------------------------------------------------

    def _generate_tool_configs(self, state: ProjectContext, instructions_md: str, artifacts: list[AIArtifact]) -> None:
        skill = self.get_skill(GenerateToolConfigSkill.name)
        project_context_summary = self._build_project_context_summary(state)

        for tool in TOOL_CONFIGS:
            template_path = TOOL_TEMPLATES_DIR / tool["template_file"]
            try:
                raw_template = template_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.error("ai-dev-setup: tool template not found: %s", template_path)
                continue

            rendered_skeleton = Template(raw_template).render(
                project_name=state.project_name, project_description=state.project_description
            )
            inputs = GenerateToolConfigSkill.build_inputs(
                tool_name=tool["tool_name"],
                tool_template=rendered_skeleton,
                instructions_md_content=instructions_md,
                project_context_summary=project_context_summary,
            )
            result = self.invoke_skill(skill, inputs, state, component_name=f"tool-config:{tool['tool_name']}")
            if result is None:
                continue

            artifacts.append(
                AIArtifact(
                    type="tool_config",
                    filename=tool["output_filename"],
                    content=result["content"],
                    derived_from=["instructions.md"],
                    used_default=False,
                    prompt_version=skill.prompt_version,
                )
            )

    def _build_project_context_summary(self, state: ProjectContext) -> str:
        tech = ", ".join(item.technology for item in state.tech_stack) or "(none extracted)"
        components = ", ".join(component.name for component in state.components) or "(none extracted)"
        return (
            f"{state.project_name}: {state.project_description}\n"
            f"Tech stack: {tech}\n"
            f"Components: {components}"
        )
