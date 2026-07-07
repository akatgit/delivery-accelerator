"""Review QA Agent output schemas (BRD section 12.2, FR-2.10)."""

from pydantic import BaseModel, Field


class Contradiction(BaseModel):
    """Two reviewer findings that make opposing recommendations (FR-2.10.3).

    The QA agent surfaces contradictions but does not resolve them; ``resolution``
    is populated later by the human at the approval gate (FR-3.6).
    """

    finding_id_a: str
    finding_id_b: str
    domain_a: str
    domain_b: str
    description: str
    resolution: str | None = Field(
        default=None, description="Set by the human when resolving the contradiction (FR-3.6)."
    )


class ReviewQAResult(BaseModel):
    """Output of the Review QA Agent: a validation pass over the aggregated review,
    covering deduplication, contradiction detection, severity normalization,
    actionability, and coverage (FR-2.10.1 through FR-2.10.8).
    """

    quality_score: int = Field(ge=1, le=10)
    duplicates_found: int
    contradictions: list[Contradiction] = Field(default_factory=list)
    severity_normalizations: list[dict] = Field(default_factory=list)
    low_quality_findings: list[str] = Field(
        default_factory=list, description="Finding IDs flagged as low-quality (FR-2.10.5)."
    )
    coverage_warnings: list[str] = Field(
        default_factory=list,
        description="Domains with suspicious zero findings for a complex architecture (FR-2.10.6).",
    )
    summary: str
