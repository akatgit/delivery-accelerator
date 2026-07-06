"""BaseSkill: the reusable, testable unit of LLM work (ARCHITECTURE_v2.0.md section 3.3).

A skill takes specific inputs and produces a specific Pydantic-validated output. It
owns its own prompt template, chunking (for large inputs), retries, and output
validation. Agents are thin orchestrators that call skills; skills are where every
LLM call actually happens.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from jinja2 import Template
from langchain_anthropic import ChatAnthropic
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable
from pydantic import BaseModel, RootModel, ValidationError

from backend.config import settings
from backend.schemas.pipeline import DecisionEntry

logger = logging.getLogger(__name__)

# Rough heuristic used to convert the token-based budgets in ARCHITECTURE_v2.0.md
# section 4.1 (chunk_size=6000 tokens, overlap=500 tokens) into character counts for
# RecursiveCharacterTextSplitter, which splits on characters, not tokens.
CHARS_PER_TOKEN = 4

_VERSION_HEADER_RE = re.compile(r"^#\s*version:\s*(\S+)", re.IGNORECASE)


class SkillFailedError(Exception):
    """Raised when a skill exhausts all retries (both output-validation retries and
    LLM-call retries) without producing a valid result.

    Callers (agents) are expected to catch this, log it to
    ``ProjectContext.failed_components``, and continue with remaining work
    (ARCHITECTURE_v2.0.md section 4.2, layer 3 — graceful degradation).
    """

    def __init__(self, skill_name: str, message: str, *, cause: Exception | None = None):
        self.skill_name = skill_name
        self.message = message
        self.cause = cause
        super().__init__(f"[{skill_name}] {message}")


class BaseSkill:
    """Base class for all skills. Subclasses set the class attributes below and may
    override ``_build_prompt_inputs`` if they need to pre-process raw inputs before
    template rendering.
    """

    name: str
    description: str
    prompt_template_path: str
    output_schema: type[BaseModel]
    max_input_tokens: int = 6000
    chunk_merge_strategy: Literal["union", "merge_and_deduplicate"] = "union"

    def __init__(self, llm: ChatAnthropic | None = None):
        if not getattr(self, "name", None):
            raise ValueError(f"{type(self).__name__} must define a class-level 'name'")
        if not getattr(self, "output_schema", None):
            raise ValueError(f"{type(self).__name__} must define an 'output_schema'")
        self.llm = llm or ChatAnthropic(
            model=settings.model_name, api_key=settings.anthropic_api_key
        )
        self._prompt_template, self.prompt_version = self._load_prompt_template()
        logger.debug(
            "Loaded skill '%s' (prompt v%s) from %s",
            self.name,
            self.prompt_version,
            self.prompt_template_path,
        )

    # ------------------------------------------------------------------
    # Prompt template loading (ARCHITECTURE_v2.0.md section 4.3, 7.1)
    # ------------------------------------------------------------------

    def _load_prompt_template(self) -> tuple[str, str]:
        path = Path(self.prompt_template_path)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise SkillFailedError(
                self.name, f"Prompt template not found at {path}", cause=exc
            ) from exc

        version = "0.0.0"
        for line in text.splitlines()[:5]:
            match = _VERSION_HEADER_RE.match(line.strip())
            if match:
                version = match.group(1)
                break
        else:
            logger.warning(
                "Skill '%s' prompt template has no '# version:' header; defaulting to %s",
                self.name,
                version,
            )
        return text, version

    def _render_prompt(self, inputs: dict) -> str:
        return Template(self._prompt_template).render(**inputs)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def invoke(
        self,
        inputs: dict,
        *,
        agent_name: str | None = None,
        decision_log: list[DecisionEntry] | None = None,
    ) -> dict:
        """Run this skill end to end: render the prompt, chunk if needed, call the
        LLM with retries, validate the output, and log the decision.

        Raises ``SkillFailedError`` if the skill cannot produce a valid result after
        all retries (graceful degradation is the caller's responsibility).
        """
        logger.info("Invoking skill '%s' (prompt v%s)", self.name, self.prompt_version)
        result_model = self._run(
            inputs,
            langsmith_extra={
                "metadata": {"skill": self.name, "prompt_version": self.prompt_version}
            },
        )
        result = result_model.model_dump(mode="json")
        self._record_decision(inputs, result, agent_name=agent_name, decision_log=decision_log)
        logger.info("Skill '%s' completed successfully", self.name)
        return result

    @traceable(run_type="chain")
    def _run(self, inputs: dict) -> BaseModel:
        rendered = self._render_prompt(inputs)
        if self._estimate_tokens(rendered) > self.max_input_tokens:
            logger.info(
                "Skill '%s' input (~%d tokens) exceeds max_input_tokens=%d; chunking",
                self.name,
                self._estimate_tokens(rendered),
                self.max_input_tokens,
            )
            return self._invoke_chunked(inputs)
        raw = self._call_llm_with_retry(rendered)
        return self._validate_or_correct(rendered, raw)

    # ------------------------------------------------------------------
    # Layer 2 — retry logic with exponential backoff (section 4.2)
    # ------------------------------------------------------------------

    def _call_llm_with_retry(self, prompt: str) -> str:
        backoff_seconds = 1.0
        last_exc: Exception | None = None
        for attempt in range(settings.max_retries + 1):
            try:
                response = self.llm.invoke(prompt)
                return response.content if hasattr(response, "content") else str(response)
            except Exception as exc:  # LLM timeout, rate limit, transport errors
                last_exc = exc
                if attempt < settings.max_retries:
                    logger.warning(
                        "Skill '%s' LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                        self.name,
                        attempt + 1,
                        settings.max_retries + 1,
                        exc,
                        backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                else:
                    logger.error(
                        "Skill '%s' LLM call failed after %d attempts: %s",
                        self.name,
                        settings.max_retries + 1,
                        exc,
                    )
        raise SkillFailedError(
            self.name, f"LLM call failed after {settings.max_retries + 1} attempts", cause=last_exc
        )

    # ------------------------------------------------------------------
    # Layer 1 — output validation with error-correction retry (section 4.2)
    # ------------------------------------------------------------------

    def _validate_or_correct(self, prompt: str, raw_output: str) -> BaseModel:
        current_output = raw_output
        last_error: Exception | None = None
        for attempt in range(settings.max_retries + 1):
            try:
                parsed = self._extract_json(current_output)
                return self.output_schema.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                if attempt < settings.max_retries:
                    logger.warning(
                        "Skill '%s' output failed validation (attempt %d/%d): %s — "
                        "retrying with error-correction prompt",
                        self.name,
                        attempt + 1,
                        settings.max_retries + 1,
                        exc,
                    )
                    correction_prompt = (
                        f"{prompt}\n\n"
                        f"Your previous output was invalid: {exc}. "
                        "Please fix and return valid JSON."
                    )
                    current_output = self._call_llm_with_retry(correction_prompt)
                else:
                    logger.error(
                        "Skill '%s' output still invalid after %d attempts: %s",
                        self.name,
                        settings.max_retries + 1,
                        exc,
                    )
        raise SkillFailedError(
            self.name,
            f"Output validation failed after {settings.max_retries + 1} attempts",
            cause=last_error,
        )

    @staticmethod
    def _extract_json(text: str) -> Any:
        """Parse the LLM's raw output as JSON, tolerating surrounding prose or
        markdown code fences."""
        text = text.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1)
        return json.loads(text)

    # ------------------------------------------------------------------
    # Map-reduce chunking (section 4.1)
    # ------------------------------------------------------------------

    def _find_chunk_target(self, inputs: dict) -> str:
        """Identify which input field holds the bulk document text to split. Absent
        an explicit convention, the largest string-valued input is assumed to be the
        document being chunked; all other inputs are held constant across chunks."""
        string_inputs = {k: v for k, v in inputs.items() if isinstance(v, str)}
        if not string_inputs:
            raise SkillFailedError(
                self.name,
                "Input exceeds max_input_tokens but contains no chunkable string field",
            )
        return max(string_inputs, key=lambda k: len(string_inputs[k]))

    def _invoke_chunked(self, inputs: dict) -> BaseModel:
        target_key = self._find_chunk_target(inputs)
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.max_input_tokens * CHARS_PER_TOKEN,
            chunk_overlap=settings.chunk_overlap * CHARS_PER_TOKEN,
        )
        chunks = splitter.split_text(inputs[target_key])
        logger.info("Skill '%s' split '%s' into %d chunk(s)", self.name, target_key, len(chunks))

        outputs: list[BaseModel] = []
        for i, chunk in enumerate(chunks):
            chunk_inputs = {**inputs, target_key: chunk}
            rendered = self._render_prompt(chunk_inputs)
            raw = self._call_llm_with_retry(rendered)
            outputs.append(self._validate_or_correct(rendered, raw))
            logger.debug("Skill '%s' processed chunk %d/%d", self.name, i + 1, len(chunks))

        return self._merge_chunk_outputs(outputs)

    def _merge_chunk_outputs(self, outputs: list[BaseModel]) -> BaseModel:
        if not outputs:
            raise SkillFailedError(self.name, "No chunk outputs to merge")
        if len(outputs) == 1:
            return outputs[0]

        model_cls = type(outputs[0])

        if isinstance(outputs[0], RootModel):
            merged_items: list = []
            for output in outputs:
                root_value = output.root
                merged_items.extend(root_value if isinstance(root_value, list) else [root_value])
            if self.chunk_merge_strategy == "merge_and_deduplicate":
                merged_items = self._deduplicate(merged_items)
            return model_cls(merged_items)

        merged_data: dict = {}
        for field_name in model_cls.model_fields:
            values = [getattr(output, field_name) for output in outputs]
            if isinstance(values[0], list):
                combined = [item for value in values for item in value]
                if self.chunk_merge_strategy == "merge_and_deduplicate":
                    combined = self._deduplicate(combined)
                merged_data[field_name] = combined
            else:
                merged_data[field_name] = next((v for v in values if v is not None), values[0])
        return model_cls(**merged_data)

    @staticmethod
    def _deduplicate(items: list) -> list:
        seen: set[str] = set()
        deduped = []
        for item in items:
            key = item.model_dump_json() if isinstance(item, BaseModel) else json.dumps(
                item, sort_keys=True, default=str
            )
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        return deduped

    # ------------------------------------------------------------------
    # Decision log (FR-6.2, ARCHITECTURE_v2.0.md section 4.3)
    # ------------------------------------------------------------------

    def _record_decision(
        self,
        inputs: dict,
        output: dict,
        *,
        agent_name: str | None,
        decision_log: list[DecisionEntry] | None,
    ) -> None:
        if decision_log is None:
            return
        decision_log.append(
            DecisionEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent=agent_name or "unknown",
                skill=self.name,
                prompt_version=self.prompt_version,
                decision=f"{self.name} inputs: {self._summarize(inputs)}",
                rationale=f"{self.name} output: {self._summarize(output)}",
                alternatives_considered=[],
                context_refs=list(inputs.keys()),
                standard_refs=[k for k in inputs if "standard" in k.lower()],
            )
        )

    @staticmethod
    def _summarize(value: Any, max_len: int = 300) -> str:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        return text if len(text) <= max_len else text[: max_len - 3] + "..."
