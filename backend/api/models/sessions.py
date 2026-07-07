"""Request/response models for session endpoints (ARCHITECTURE_v2.0.md
section 10.1)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.api.session_store import SessionRecord


class SessionCreateRequest(BaseModel):
    project_name: str = Field(default="Untitled Project")
    project_description: str = Field(default="")


class SessionResponse(BaseModel):
    id: str
    project_name: str
    project_description: str
    created_at: str
    current_stage: str

    @classmethod
    def from_record(cls, record: SessionRecord) -> "SessionResponse":
        return cls(
            id=record.id,
            project_name=record.project_name,
            project_description=record.project_description,
            created_at=record.created_at,
            current_stage=record.current_stage,
        )


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
