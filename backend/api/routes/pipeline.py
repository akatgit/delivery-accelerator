"""Pipeline endpoints (ARCHITECTURE_v2.0.md section 10.1)."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.api.graph_access import get_pipeline_state, get_state_snapshot, retry_reviewer_domain
from backend.api.graph_runner import resume_pipeline_background, start_pipeline_background
from backend.api.models.pipeline import (
    ApprovalRequest,
    ApprovalResponse,
    ArtifactsResponse,
    DecisionLogResponse,
    ExtractionConfirmRequest,
    ExtractionResponse,
    ReuploadRequest,
    ReuploadResponse,
    RetryDomainResponse,
    ReviewQualityResponse,
    ReviewResponse,
    ScaffoldingResponse,
    StartPipelineResponse,
    StatusResponse,
    TraceResponse,
)
from backend.api.routes.sessions import require_session
from backend.api.session_store import get_session_store
from backend.config import settings
from backend.graph.state import PipelineState
from backend.schemas.review import ReviewDomain
from backend.tools.aggregator import aggregate_reviews

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["pipeline"])


def _require_pipeline_state(session_id: str) -> PipelineState:
    state = get_pipeline_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Pipeline has not started yet")
    return state


@router.post("/{session_id}/start", response_model=StartPipelineResponse)
async def start_pipeline(session_id: str) -> StartPipelineResponse:
    store = get_session_store()
    record = require_session(session_id)

    initial_state = PipelineState(
        project_name=record.project_name,
        project_description=record.project_description,
        raw_documents=record.raw_documents,
        standards_dir=record.standards_dir,
    )
    start_pipeline_background(session_id, initial_state, store)
    store.update_session(session_id, current_stage="running")
    return StartPipelineResponse(session_id=session_id)


@router.get("/{session_id}/status", response_model=StatusResponse)
async def get_status(session_id: str) -> StatusResponse:
    record = require_session(session_id)
    snapshot = get_state_snapshot(session_id)
    if not snapshot.values:
        return StatusResponse(session_id=session_id, current_stage=record.current_stage, review_iteration=0)

    state = PipelineState.model_validate(snapshot.values)
    current_stage = state.current_stage.value if hasattr(state.current_stage, "value") else str(state.current_stage)
    return StatusResponse(
        session_id=session_id,
        current_stage=current_stage,
        review_iteration=state.review_iteration,
        paused_at=snapshot.next[0] if snapshot.next else None,
        failed_components=[fc.component for fc in state.failed_components],
    )


@router.get("/{session_id}/extraction", response_model=ExtractionResponse)
async def get_extraction(session_id: str) -> ExtractionResponse:
    require_session(session_id)
    return ExtractionResponse(project_context=_require_pipeline_state(session_id))


@router.post("/{session_id}/extraction/confirm")
async def confirm_extraction(session_id: str, request: ExtractionConfirmRequest) -> dict:
    """FR-1.7: extraction is shown to the user for verification. The graph
    itself doesn't pause specifically for this today (only at the two human
    gates), so this just records the confirmation; review proceeds via the
    review-board fan-out that already runs right after parse_documents."""
    require_session(session_id)
    return {"session_id": session_id, "confirmed": request.confirmed}


@router.get("/{session_id}/review", response_model=ReviewResponse)
async def get_review(session_id: str) -> ReviewResponse:
    require_session(session_id)
    state = _require_pipeline_state(session_id)
    failed_domains = [domain.value for domain in ReviewDomain if domain not in {r.domain for r in state.reviews}]
    result = aggregate_reviews(state.reviews, failed_domains)
    return ReviewResponse(
        overall_score=state.overall_score,
        threshold_passed=result["threshold_passed"],
        reviews=state.reviews,
        findings=[finding.model_dump(mode="json") for finding in result["findings"]],
        remediation_summary=state.remediation_summary,
    )


@router.get("/{session_id}/review/quality", response_model=ReviewQualityResponse)
async def get_review_quality(session_id: str) -> ReviewQualityResponse:
    require_session(session_id)
    return ReviewQualityResponse(review_qa=_require_pipeline_state(session_id).review_qa)


@router.post("/{session_id}/approve", response_model=ApprovalResponse)
async def approve(session_id: str, request: ApprovalRequest) -> ApprovalResponse:
    """FR-3: human gate decision. `human_gate_1`/`human_gate_2`
    (`graph/nodes.py`) validate the resume payload's shape themselves and
    re-interrupt with an error if it's invalid, so this endpoint just passes
    it through rather than duplicating that validation."""
    store = get_session_store()
    require_session(session_id)
    snapshot = get_state_snapshot(session_id)
    if not snapshot.values or not snapshot.next:
        raise HTTPException(status_code=409, detail="Pipeline is not currently paused for approval")

    resume_value = {
        "decision": request.decision,
        "overrides": request.overrides,
        "contradiction_resolutions": request.contradiction_resolutions,
        "justification": request.justification,
    }
    resume_pipeline_background(session_id, resume_value, store)
    return ApprovalResponse(session_id=session_id, accepted=True)


@router.post("/{session_id}/reupload", response_model=ReuploadResponse)
async def reupload(session_id: str, request: ReuploadRequest) -> ReuploadResponse:
    """FR-3.5: revised documents trigger re-review. Implemented as an update
    to the stored raw documents followed by a "revise" decision at
    human_gate_1, so it goes through the same validated re-review path as a
    manual revise rather than a separate ad hoc restart mechanism."""
    store = get_session_store()
    record = require_session(session_id)

    documents = dict(record.raw_documents)
    documents.update(request.documents)
    store.update_session(session_id, raw_documents=documents)

    snapshot = get_state_snapshot(session_id)
    if not snapshot.values or not snapshot.next or snapshot.next[0] != "human_gate_1":
        raise HTTPException(
            status_code=409, detail="Reupload is only supported while paused at the review approval gate"
        )

    state = PipelineState.model_validate(snapshot.values)
    resume_pipeline_background(
        session_id,
        {"decision": "revise", "justification": "Revised documents uploaded for re-review."},
        store,
    )
    return ReuploadResponse(session_id=session_id, review_iteration=state.review_iteration + 1)


@router.post("/{session_id}/retry/{domain}", response_model=RetryDomainResponse)
async def retry_domain(session_id: str, domain: str) -> RetryDomainResponse:
    """FR-2.9: retry a single failed reviewer without re-running the whole
    review board."""
    require_session(session_id)
    try:
        review_domain = ReviewDomain(domain)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown domain '{domain}'")

    status = retry_reviewer_domain(session_id, review_domain)
    if status == "no_pipeline_state":
        raise HTTPException(status_code=409, detail="Pipeline has not started yet")
    return RetryDomainResponse(session_id=session_id, domain=domain, status=status)


@router.get("/{session_id}/artifacts", response_model=ArtifactsResponse)
async def get_artifacts(session_id: str) -> ArtifactsResponse:
    require_session(session_id)
    return ArtifactsResponse(artifacts=_require_pipeline_state(session_id).ai_artifacts)


@router.get("/{session_id}/scaffolding")
async def get_scaffolding(session_id: str, download: bool = False):
    """Section 5.10: the user previews the file tree *before* deciding to
    approve at human_gate_2 -- `scaffolding_structure` (the file manifest)
    exists as soon as `generate_scaffolding` runs, well before the .zip is
    actually built (that only happens after the human approves, at
    `build_zip`). So preview only needs the manifest; `download=true` is the
    one case that needs the zip to already exist on disk.
    """
    require_session(session_id)
    state = _require_pipeline_state(session_id)
    if not state.scaffolding_structure:
        raise HTTPException(status_code=404, detail="Scaffolding has not been built yet")

    if download:
        if not state.scaffold_zip_path:
            raise HTTPException(status_code=404, detail="Scaffolding has not been approved/packaged yet")
        zip_path = Path(state.scaffold_zip_path)
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="Scaffolding zip file is missing on disk")
        return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")

    manifest = state.scaffolding_structure.get("files", {})
    return ScaffoldingResponse(
        file_count=len(manifest),
        files=sorted(manifest.keys()),
        zip_path=state.scaffold_zip_path,
        download_url=f"/api/sessions/{session_id}/scaffolding?download=true",
    )


@router.get("/{session_id}/decision-log", response_model=DecisionLogResponse)
async def get_decision_log(session_id: str) -> DecisionLogResponse:
    require_session(session_id)
    return DecisionLogResponse(entries=_require_pipeline_state(session_id).decision_log)


@router.get("/{session_id}/trace", response_model=TraceResponse)
async def get_trace(session_id: str) -> TraceResponse:
    """FR-6.1: LangSmith trace URL. LangSmith organizes traces by project,
    not by an ID this API controls, so this links to the configured
    LangSmith project dashboard rather than one specific run -- there's no
    stable per-session run ID plumbed through today."""
    require_session(session_id)
    if not settings.langsmith_api_key:
        return TraceResponse(trace_url=None)
    return TraceResponse(trace_url=f"https://smith.langchain.com/projects/{settings.langsmith_project}")
