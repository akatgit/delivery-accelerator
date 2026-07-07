"""Session endpoints (ARCHITECTURE_v2.0.md section 10.1)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.api.models.sessions import SessionCreateRequest, SessionListResponse, SessionResponse
from backend.api.session_store import SessionRecord, get_session_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def require_session(session_id: str) -> SessionRecord:
    """Shared by every route module keyed off `{session_id}` -- 404s early
    and consistently rather than each route re-implementing the check."""
    record = get_session_store().get_session(session_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return record


@router.post("", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest) -> SessionResponse:
    record = get_session_store().create_session(request.project_name, request.project_description)
    return SessionResponse.from_record(record)


@router.get("", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """For the session-reuse dropdown (FR-1.11, section 14.5)."""
    records = get_session_store().list_sessions()
    return SessionListResponse(sessions=[SessionResponse.from_record(r) for r in records])


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    return SessionResponse.from_record(require_session(session_id))
