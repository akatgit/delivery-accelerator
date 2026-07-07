"""Pipeline state and audit-trail schemas (BRD section 12.4, section 11, FR-3.8, FR-6)."""

from enum import Enum

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    """Stages of the pipeline flow, in execution order (section 11)."""

    DOCUMENT_PARSING = "document_parsing"
    EXTRACTION_PREVIEW = "extraction_preview"
    REVIEW_BOARD = "review_board"
    REVIEW_AGGREGATION = "review_aggregation"
    REVIEW_QA = "review_qa"
    HUMAN_APPROVAL_REVIEW = "human_approval_review"
    CONTEXT_SYNTHESIS = "context_synthesis"
    AI_DEVELOPMENT_SETUP = "ai_development_setup"
    CONSISTENCY_CHECK = "consistency_check"
    PROJECT_SCAFFOLDING = "project_scaffolding"
    HUMAN_APPROVAL_FINAL = "human_approval_final"
    COMPLETED = "completed"


class HumanDecisionAction(str, Enum):
    """Actions a human can take at an approval gate (FR-3.2 through FR-3.6)."""

    ACCEPT = "accept"
    OVERRIDE = "override"
    REVISE = "revise"
    RESOLVE_CONTRADICTION = "resolve_contradiction"


class FailedComponent(BaseModel):
    """A pipeline component (agent/skill) that failed after exhausting retries,
    logged so the pipeline can continue and the user can trigger a manual re-run
    (FR-2.9, FR-6.6)."""

    component: str
    error: str
    retry_count: int
    timestamp: str


class HumanDecision(BaseModel):
    """A single human action taken at an approval gate: accepting, overriding, or
    revising findings, or resolving a contradiction (FR-3.2 through FR-3.6, FR-3.8)."""

    timestamp: str
    action: HumanDecisionAction
    finding_ids: list[str] = Field(default_factory=list)
    justification: str | None = None
    domain: str | None = None


class DecisionEntry(BaseModel):
    """An entry in the full decision log, capturing every agent/skill decision with
    its rationale and the standards or context that informed it (FR-6.2, FR-4.5)."""

    timestamp: str
    agent: str
    skill: str | None = None
    prompt_version: str | None = None
    decision: str
    rationale: str
    alternatives_considered: list[str] = Field(default_factory=list)
    context_refs: list[str] = Field(default_factory=list)
    standard_refs: list[str] = Field(default_factory=list)
