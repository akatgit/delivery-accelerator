"""Request/response models for document and org-standards endpoints
(ARCHITECTURE_v2.0.md section 10.1; BRD_v2.0.md FR-1)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    session_id: str
    document_type: str
    filename: str
    character_count: int


class StandardsUploadResponse(BaseModel):
    session_id: str
    loaded_categories: list[str]
    missing_categories: list[str]
    conflicts_found: int


class StandardsReuseResponse(BaseModel):
    session_id: str
    reused_from: str
    loaded_categories: list[str]


class StandardsCoverageResponse(BaseModel):
    loaded_categories: list[str]
    missing_categories: list[str]


class ConflictItem(BaseModel):
    category_a: str
    statement_a: str
    category_b: str
    statement_b: str
    description: str
    resolution: str | None = None


class ConflictsResponse(BaseModel):
    conflicts: list[ConflictItem]


class ConflictResolutionEntry(BaseModel):
    category_a: str
    category_b: str
    resolution: str = Field(min_length=1, description="Which standard takes priority, or how the conflict is acknowledged.")


class ConflictResolutionRequest(BaseModel):
    resolutions: list[ConflictResolutionEntry]


class ConflictResolutionResponse(BaseModel):
    resolved_count: int
    remaining_unresolved: int
