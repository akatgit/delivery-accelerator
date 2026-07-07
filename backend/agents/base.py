"""BaseAgent: the thin-orchestrator layer (ARCHITECTURE_v2.0.md section 3.3).

Agents decide WHAT skills to call and in WHAT order. They contain no LLM logic of
their own — every LLM call happens inside a skill. Agents are also responsible for
graceful degradation: if a skill fails after its own retries, the agent logs it to
``ProjectContext.failed_components`` and continues with the rest of its work
(ARCHITECTURE_v2.0.md section 4.2, layer 3).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from langsmith import traceable

from backend.config import settings
from backend.schemas.pipeline import FailedComponent
from backend.schemas.project_context import ProjectContext
from backend.skills.base import BaseSkill, SkillFailedError

logger = logging.getLogger(__name__)

BASE_RULES_PATH = Path(__file__).resolve().parent.parent / "prompts" / "instructions" / "base_rules.md"


def _load_base_instructions() -> str:
    try:
        return BASE_RULES_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("Base rules file not found at %s; agents will run without them", BASE_RULES_PATH)
        return ""


class BaseAgent(ABC):
    """Base class for every agent in the pipeline.

    Subclasses implement ``run(state) -> state``. Every subclass's ``run`` is
    automatically wrapped in LangSmith tracing (see ``__init_subclass__``), so
    concrete agents don't need to think about tracing themselves.
    """

    name: str
    skills: list[BaseSkill]
    base_instructions: str

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        if "run" in cls.__dict__:
            cls.run = traceable(run_type="chain", name=cls.__name__)(cls.__dict__["run"])

    def __init__(self, name: str, skills: list[BaseSkill] | None = None):
        self.name = name
        self.skills = skills or []
        self.base_instructions = _load_base_instructions()
        logger.debug("Initialized agent '%s' with %d skill(s)", self.name, len(self.skills))

    @abstractmethod
    def run(self, state: ProjectContext) -> ProjectContext:
        """Execute this agent's orchestration logic and return the updated state.

        Subclasses hold no business logic of their own beyond deciding which skills
        to call, in what order, and how to fold results back into ``state``.
        """
        raise NotImplementedError

    def get_skill(self, name: str) -> BaseSkill:
        """Look up one of this agent's skills by name."""
        for skill in self.skills:
            if skill.name == name:
                return skill
        raise KeyError(f"Agent '{self.name}' has no skill named '{name}'")

    def invoke_skill(
        self,
        skill: BaseSkill,
        inputs: dict,
        state: ProjectContext,
        *,
        component_name: str | None = None,
    ) -> dict | None:
        """Invoke a skill on behalf of this agent, catching ``SkillFailedError``.

        On failure, logs a ``FailedComponent`` to ``state.failed_components`` and
        returns ``None`` so the agent can continue with its remaining work
        (graceful degradation — ARCHITECTURE_v2.0.md section 4.2, layer 3).
        """
        component = component_name or skill.name
        try:
            logger.info("Agent '%s' invoking skill '%s'", self.name, skill.name)
            result = skill.invoke(inputs, agent_name=self.name, decision_log=state.decision_log)
            logger.info("Agent '%s' skill '%s' succeeded", self.name, skill.name)
            return result
        except SkillFailedError as exc:
            logger.error("Agent '%s' skill '%s' failed: %s", self.name, skill.name, exc)
            state.failed_components.append(
                FailedComponent(
                    component=component,
                    error=str(exc),
                    retry_count=settings.max_retries,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )
            return None
