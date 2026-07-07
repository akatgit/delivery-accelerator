"""Request/response models for pipeline endpoints (ARCHITECTURE_v2.0.md
section 10.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.schemas.artifacts import AIArtifact
from backend.schemas.pipeline import DecisionEntry
from backend.schemas.project_context import ProjectContext
from backend.schemas.review import ReviewResult
from backend.schemas.review_qa import ReviewQAResult


class StartPipelineResponse(BaseModel):
    session_id: str
    status: str = "started"


class StatusResponse(BaseModel):
    session_id: str
    current_stage: str
    review_iteration: int
    paused_at: str | None = None
    failed_components: list[str] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    project_context: ProjectContext


class ExtractionConfirmRequest(BaseModel):
    confirmed: bool = True


class ReviewResponse(BaseModel):
    overall_score: float | None
    threshold_passed: bool
    reviews: list[ReviewResult]
    findings: list[dict]
    remediation_summary: str | None


class ReviewQualityResponse(BaseModel):
    review_qa: ReviewQAResult | None


class ApprovalRequest(BaseModel):
    """Passed straight through as the graph's `Command(resume=...)` payload;
    `human_gate_1`/`human_gate_2` (`graph/nodes.py`) validate its shape
    themselves and re-interrupt with an error if it's invalid, rather than
    this model duplicating that validation."""

    decision: str
    overrides: list[dict] = Field(default_factory=list)
    contradiction_resolutions: list[dict] = Field(default_factory=list)
    justification: str | None = None


class ApprovalResponse(BaseModel):
    session_id: str
    accepted: bool


class ReuploadRequest(BaseModel):
    documents: dict[str, str] = Field(default_factory=dict)


class ReuploadResponse(BaseModel):
    session_id: str
    review_iteration: int


class RetryDomainResponse(BaseModel):
    session_id: str
    domain: str
    status: str


class ArtifactsResponse(BaseModel):
    artifacts: list[AIArtifact]


class ScaffoldingResponse(BaseModel):
    file_count: int
    files: list[str]
    zip_path: str | None
    download_url: str | None = None


class DecisionLogResponse(BaseModel):
    entries: list[DecisionEntry]


class TraceResponse(BaseModel):
    trace_url: str | None
