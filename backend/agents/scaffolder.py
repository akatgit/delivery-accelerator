"""ProjectScaffolderAgent (ARCHITECTURE_v2.0.md section 5.9; BRD_v2.0.md FR-5).

Generates the project skeleton (folder structure, boilerplate config files,
pattern samples), embeds all AI development artifacts in their designated
locations (FR-5.4), and produces a README (FR-5.5) -- all assembled into one
flat file manifest (`ProjectContext.scaffolding_structure["files"]`). No
skill exists for README generation (section 5.9 names only three skills), so
it's assembled deterministically from already-known state, matching the
"deterministic -> code, not LLM judgment" rule used throughout this project.

Outputs the file manifest; a separate deterministic tool (`zip_builder`)
turns it into the downloadable .zip archive.
"""

from __future__ import annotations

import logging
import re

from backend.agents.base import BaseAgent
from backend.schemas.project_context import ProjectContext
from backend.skills.base import BaseSkill
from backend.skills.scaffolding.generate_config_file import GenerateConfigFileSkill
from backend.skills.scaffolding.generate_folder_structure import GenerateFolderStructureSkill
from backend.skills.scaffolding.generate_pattern_sample import GeneratePatternSampleSkill

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


# FR-5.2: Docker, environment configs, CI/CD pipeline definitions.
CONFIG_FILES = [
    ("Dockerfile", "Dockerfile"),
    ("docker-compose configuration", "docker-compose.yml"),
    ("environment config (.env.example)", ".env.example"),
    ("CI/CD pipeline definition", ".github/workflows/ci.yml"),
]


class ProjectScaffolderAgent(BaseAgent):
    """Generates the project skeleton and file manifest for the final .zip."""

    def __init__(self, skills: list[BaseSkill] | None = None):
        super().__init__(
            name="project-scaffolder",
            skills=skills
            or [
                GenerateFolderStructureSkill(),
                GenerateConfigFileSkill(),
                GeneratePatternSampleSkill(),
            ],
        )

    def run(self, state: ProjectContext) -> ProjectContext:
        manifest: dict[str, str] = {}

        folder_structure = self._run_generate_folder_structure(state)
        self._add_config_files(state, manifest)
        self._add_pattern_samples(state, manifest)
        self._embed_ai_artifacts(state, manifest)
        self._add_readme(state, manifest)

        state.scaffolding_structure = {"folder_structure": folder_structure, "files": manifest}

        logger.info(
            "project-scaffolder: assembled %d file(s), folder_structure %s",
            len(manifest),
            "generated" if folder_structure else "empty",
        )
        return state

    # ------------------------------------------------------------------

    def _run_generate_folder_structure(self, state: ProjectContext) -> dict:
        skill = self.get_skill(GenerateFolderStructureSkill.name)
        inputs = GenerateFolderStructureSkill.build_inputs(
            state.components, state.tech_stack, state.existing_codebase
        )
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is None:
            return {}
        return result["tree"]

    def _add_config_files(self, state: ProjectContext, manifest: dict[str, str]) -> None:
        skill = self.get_skill(GenerateConfigFileSkill.name)
        for config_type, filename in CONFIG_FILES:
            inputs = GenerateConfigFileSkill.build_inputs(config_type, state.org_standards, state.tech_stack)
            result = self.invoke_skill(skill, inputs, state, component_name=f"config-file:{config_type}")
            if result is None:
                continue
            manifest[filename] = result["content"]

    def _add_pattern_samples(self, state: ProjectContext, manifest: dict[str, str]) -> None:
        skill = self.get_skill(GeneratePatternSampleSkill.name)
        instructions_md = next((a.content for a in state.ai_artifacts if a.type == "instructions_md"), "")

        for pattern in state.patterns:
            inputs = GeneratePatternSampleSkill.build_inputs(pattern, state.org_standards, instructions_md)
            result = self.invoke_skill(skill, inputs, state, component_name=f"pattern-sample:{pattern.name}")
            if result is None:
                continue
            slug = _slugify(pattern.name)
            manifest[f"patterns/{slug}/{slug}.py"] = result["implementation"]
            manifest[f"patterns/{slug}/test_{slug}.py"] = result["test_file"]
            manifest[f"patterns/{slug}/USAGE.md"] = result["usage_header"]

    def _embed_ai_artifacts(self, state: ProjectContext, manifest: dict[str, str]) -> None:
        """FR-5.4: embed all AI artifacts in their designated locations --
        each artifact's `filename` already IS that location."""
        for artifact in state.ai_artifacts:
            manifest[artifact.filename] = artifact.content

    def _add_readme(self, state: ProjectContext, manifest: dict[str, str]) -> None:
        """FR-5.5: project overview, architecture summary, onboarding guide,
        AI artifact pointers. Assembled deterministically -- no skill exists
        for this (section 5.9 names only three), and everything it needs is
        already available in state."""
        architecture_section = next(
            (a.content for a in state.ai_artifacts if a.filename == "instructions.md#architecture-principles"),
            "",
        )
        components_summary = (
            "\n".join(f"- **{c.name}** ({c.type}): {c.description}" for c in state.components)
            or "(none extracted)"
        )
        artifact_pointers = (
            "\n".join(f"- `{a.filename}` ({a.type})" for a in state.ai_artifacts) or "(none generated)"
        )

        manifest["README.md"] = f"""# {state.project_name}

{state.project_description}

## Architecture

{components_summary}

{architecture_section}

## Onboarding

1. Read `instructions.md` for project-wide engineering standards.
2. Review the samples under `patterns/` for reference implementations.
3. Use the AI assistant configs (`.cursorrules`, `.github/copilot-instructions.md`,
   `slingshot.config.yaml`) for consistent AI-assisted guidance.

## AI development artifacts

{artifact_pointers}
"""
