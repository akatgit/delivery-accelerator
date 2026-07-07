"""DocumentParsingAgent (ARCHITECTURE_v2.0.md section 5.1).

Thin orchestrator: loads and categorizes org standards, detects conflicts
between them, then runs five extraction skills in strict sequence, each
receiving the context accumulated by the ones before it. All business logic
lives in the tool/skills it calls; this agent only decides what to call, in
what order, and how to fold each result back into the shared state.
"""

from __future__ import annotations

import logging

from backend.agents.base import BaseAgent
from backend.schemas.project_context import Component, Gap, NFR, ProjectContext, Story, StandardConflict, TechStackItem
from backend.skills.base import BaseSkill
from backend.skills.extraction.detect_standard_conflicts import DetectStandardConflictsSkill
from backend.skills.extraction.extract_components import ExtractComponentsSkill
from backend.skills.extraction.extract_nfrs import ExtractNFRsSkill
from backend.skills.extraction.extract_stories import ExtractStoriesSkill
from backend.skills.extraction.extract_tech_stack import ExtractTechStackSkill
from backend.skills.extraction.identify_gaps import IdentifyGapsSkill
from backend.tools.standards_loader import load_standards

logger = logging.getLogger(__name__)


class DocumentParsingAgent(BaseAgent):
    """Runs the section 5.1 extraction sequence over a session's raw uploaded
    documents and org standards, populating `ProjectContext`.

    Expects `state` to additionally expose (duck-typed, not part of the BRD
    `ProjectContext` schema -- see `PipelineState` in `backend/graph/state.py`):
    - `raw_documents: dict[str, str]` keyed by `"brd"`, `"architecture"`,
      `"stories"`, `"tech_preferences"` (FR-1.2)
    - `standards_dir: str | None`, the uploaded org standards directory (14.1)

    Missing either is treated as "not provided yet" rather than an error, so
    this agent can run on a plain `ProjectContext` in tests without either
    attribute present.
    """

    def __init__(self, skills: list[BaseSkill] | None = None):
        super().__init__(
            name="document-parser",
            skills=skills
            or [
                DetectStandardConflictsSkill(),
                ExtractTechStackSkill(),
                ExtractComponentsSkill(),
                ExtractNFRsSkill(),
                ExtractStoriesSkill(),
                IdentifyGapsSkill(),
            ],
        )

    def run(self, state: ProjectContext) -> ProjectContext:
        self._load_and_categorize_standards(state)
        self._detect_standard_conflicts(state)
        self._extract_tech_stack(state)
        self._extract_components(state)
        self._extract_nfrs(state)
        self._extract_stories(state)
        self._identify_gaps(state)
        return state

    # ------------------------------------------------------------------
    # Step 1: load + categorize org standards (deterministic tool, no LLM)
    # ------------------------------------------------------------------

    def _load_and_categorize_standards(self, state: ProjectContext) -> None:
        standards_dir = getattr(state, "standards_dir", None)
        if not standards_dir:
            logger.info("document-parser: no standards_dir set; keeping existing org_standards")
            return
        logger.info("document-parser: loading org standards from %s", standards_dir)
        state.org_standards = load_standards(standards_dir)

    # ------------------------------------------------------------------
    # Step 2: detect conflicts between org standards (LLM skill)
    # ------------------------------------------------------------------

    def _detect_standard_conflicts(self, state: ProjectContext) -> None:
        skill = self.get_skill(DetectStandardConflictsSkill.name)
        inputs = DetectStandardConflictsSkill.build_inputs(state.org_standards)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is not None:
            state.org_standards.conflicts = [StandardConflict.model_validate(item) for item in result]

    # ------------------------------------------------------------------
    # Steps 3a-3e: extraction in sequence, each on accumulated context
    # ------------------------------------------------------------------

    def _raw_document(self, state: ProjectContext, doc_type: str) -> str:
        return getattr(state, "raw_documents", {}).get(doc_type, "")

    def _extract_tech_stack(self, state: ProjectContext) -> None:
        skill = self.get_skill(ExtractTechStackSkill.name)
        inputs = ExtractTechStackSkill.build_inputs(
            self._raw_document(state, "tech_preferences"),
            self._raw_document(state, "architecture"),
        )
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is not None:
            state.tech_stack = [TechStackItem.model_validate(item) for item in result["items"]]

    def _extract_components(self, state: ProjectContext) -> None:
        skill = self.get_skill(ExtractComponentsSkill.name)
        inputs = ExtractComponentsSkill.build_inputs(
            self._raw_document(state, "architecture"),
            state.tech_stack,
        )
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is not None:
            state.components = [Component.model_validate(item) for item in result["items"]]

    def _extract_nfrs(self, state: ProjectContext) -> None:
        skill = self.get_skill(ExtractNFRsSkill.name)
        inputs = ExtractNFRsSkill.build_inputs(
            self._raw_document(state, "brd"),
            state.components,
        )
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is not None:
            state.nfrs = [NFR.model_validate(item) for item in result["items"]]

    def _extract_stories(self, state: ProjectContext) -> None:
        skill = self.get_skill(ExtractStoriesSkill.name)
        inputs = ExtractStoriesSkill.build_inputs(
            self._raw_document(state, "stories"),
            state.components,
        )
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is not None:
            state.stories = [Story.model_validate(item) for item in result["items"]]

    def _identify_gaps(self, state: ProjectContext) -> None:
        skill = self.get_skill(IdentifyGapsSkill.name)
        inputs = IdentifyGapsSkill.build_inputs(state)
        result = self.invoke_skill(skill, inputs, state, component_name=skill.name)
        if result is not None:
            state.gaps = [Gap.model_validate(item) for item in result["items"]]
