"""Document and org-standards endpoints (ARCHITECTURE_v2.0.md section 10.1;
BRD_v2.0.md FR-1).

Org-standard conflict detection runs here, eagerly, at upload time -- FR-1.5
and ARCHITECTURE_v2.0.md section 4.4 both frame it as happening "before the
pipeline starts," so it can't be deferred to `DocumentParsingAgent`'s own
`detect-standard-conflicts` step (that step also exists, inside the graph,
for when a session's standards weren't uploaded through this API at all;
the two aren't reconciled today -- see the note on `upload_standard` below).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.api.models.documents import (
    ConflictItem,
    ConflictResolutionRequest,
    ConflictResolutionResponse,
    ConflictsResponse,
    DocumentUploadResponse,
    StandardsCoverageResponse,
    StandardsReuseResponse,
    StandardsUploadResponse,
)
from backend.api.routes.sessions import require_session
from backend.api.session_store import get_session_store
from backend.config import settings
from backend.schemas.project_context import OrgStandards
from backend.skills.extraction.detect_standard_conflicts import DetectStandardConflictsSkill
from backend.tools.standards_loader import ALL_CATEGORIES, load_standards

router = APIRouter(prefix="/api/sessions", tags=["documents"])

VALID_DOCUMENT_TYPES = {"brd", "architecture", "stories", "tech_preferences"}


def _standards_dir(session_id: str) -> Path:
    return Path(settings.uploads_dir) / session_id / "standards"


def _loaded_categories(org_standards: OrgStandards) -> list[str]:
    return [category for category in ALL_CATEGORIES if getattr(org_standards, category, None)]


@router.post("/{session_id}/documents", response_model=DocumentUploadResponse)
async def upload_document(
    session_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """FR-1.1, FR-1.2: project docs (BRD, architecture, stories, tech
    preferences), tagged by document type on upload."""
    require_session(session_id)
    if document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"document_type must be one of {sorted(VALID_DOCUMENT_TYPES)}"
        )
    content = (await file.read()).decode("utf-8")
    get_session_store().add_raw_document(session_id, document_type, content)
    return DocumentUploadResponse(
        session_id=session_id,
        document_type=document_type,
        filename=file.filename or document_type,
        character_count=len(content),
    )


@router.post("/{session_id}/standards", response_model=StandardsUploadResponse)
async def upload_standard(session_id: str, file: UploadFile = File(...)) -> StandardsUploadResponse:
    """FR-1.3, FR-1.4: org standards, categorized by filename. After each
    upload, re-detects conflicts across every standard uploaded so far
    (FR-1.5) -- this is the API's own eager check, independent of (and not
    currently reconciled with) `DocumentParsingAgent`'s own
    detect-standard-conflicts step once the pipeline actually starts.
    """
    store = get_session_store()
    require_session(session_id)

    standards_dir = _standards_dir(session_id)
    standards_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    (standards_dir / (file.filename or "standard.md")).write_bytes(content)
    store.update_session(session_id, standards_dir=str(standards_dir))

    org_standards = load_standards(standards_dir)
    conflicts: list[dict] = []
    if len(_loaded_categories(org_standards)) >= 2:
        skill = DetectStandardConflictsSkill()
        inputs = DetectStandardConflictsSkill.build_inputs(org_standards)
        conflicts = skill.invoke(inputs)
    store.set_conflicts(session_id, conflicts)

    return StandardsUploadResponse(
        session_id=session_id,
        loaded_categories=_loaded_categories(org_standards),
        missing_categories=org_standards.missing_categories,
        conflicts_found=len(conflicts),
    )


@router.post("/{session_id}/standards/reuse/{source_id}", response_model=StandardsReuseResponse)
async def reuse_standards(session_id: str, source_id: str) -> StandardsReuseResponse:
    """FR-1.11, section 14.5: reuse org standards from a previous session."""
    store = get_session_store()
    require_session(session_id)
    source_record = require_session(source_id)
    if not source_record.standards_dir:
        raise HTTPException(status_code=404, detail=f"Session '{source_id}' has no uploaded standards")

    store.update_session(session_id, standards_dir=source_record.standards_dir, conflicts=source_record.conflicts)
    org_standards = load_standards(source_record.standards_dir)
    return StandardsReuseResponse(
        session_id=session_id, reused_from=source_id, loaded_categories=_loaded_categories(org_standards)
    )


@router.get("/{session_id}/standards/coverage", response_model=StandardsCoverageResponse)
async def standards_coverage(session_id: str) -> StandardsCoverageResponse:
    """FR-1.9: which standard categories are missing."""
    record = require_session(session_id)
    if not record.standards_dir:
        return StandardsCoverageResponse(loaded_categories=[], missing_categories=list(ALL_CATEGORIES))
    org_standards = load_standards(record.standards_dir)
    return StandardsCoverageResponse(
        loaded_categories=_loaded_categories(org_standards), missing_categories=org_standards.missing_categories
    )


@router.get("/{session_id}/standards/conflicts", response_model=ConflictsResponse)
async def get_conflicts(session_id: str) -> ConflictsResponse:
    """FR-1.5: conflicts detected across the uploaded org standards."""
    record = require_session(session_id)
    return ConflictsResponse(conflicts=[ConflictItem(**c) for c in record.conflicts])


@router.post("/{session_id}/standards/conflicts/resolve", response_model=ConflictResolutionResponse)
async def resolve_conflicts(session_id: str, request: ConflictResolutionRequest) -> ConflictResolutionResponse:
    """FR-1.5: the user must resolve or acknowledge each conflict (noting
    which standard takes priority) before proceeding. Matches resolutions to
    conflicts by (category_a, category_b) pair."""
    store = get_session_store()
    record = require_session(session_id)

    conflicts = [dict(c) for c in record.conflicts]
    resolved_count = 0
    for entry in request.resolutions:
        for conflict in conflicts:
            if conflict["category_a"] == entry.category_a and conflict["category_b"] == entry.category_b:
                conflict["resolution"] = entry.resolution
                resolved_count += 1

    store.set_conflicts(session_id, conflicts)
    remaining = sum(1 for c in conflicts if not c.get("resolution"))
    return ConflictResolutionResponse(resolved_count=resolved_count, remaining_unresolved=remaining)
