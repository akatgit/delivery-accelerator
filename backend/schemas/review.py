"""Review board output schemas (BRD section 12.2, 13)."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReviewDomain(str, Enum):
    """The five parallel review domains defined in FR-2.1."""

    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
    COMPLIANCE = "compliance"


class Severity(str, Enum):
    """Finding severity classification (FR-2.4)."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


class FindingStatus(str, Enum):
    """Lifecycle status of a finding as it moves through the human approval gate (FR-3)."""

    OPEN = "open"
    ACCEPTED = "accepted"
    OVERRIDDEN = "overridden"
    RESOLVED = "resolved"


class DimensionScore(BaseModel):
    """Score for a single rubric dimension within a domain review (section 13)."""

    dimension: str
    score: int = Field(ge=1, le=10)
    justification: str


class Finding(BaseModel):
    """A single review finding produced by a reviewer agent (FR-2.4, FR-2.5)."""

    id: str
    severity: Severity
    title: str
    description: str
    affected_components: list[str] = Field(default_factory=list)
    recommendation: str
    based_on: str
    status: FindingStatus = FindingStatus.OPEN
    override_justification: str | None = None
    duplicate_of: str | None = Field(
        default=None,
        description="Set by the Review QA Agent when this finding is merged into another (FR-2.10.2).",
    )
    contributing_domains: list[str] = Field(
        default_factory=list,
        description="Set by the Review QA Agent for findings merged from multiple domains (FR-2.10.2).",
    )


class ReviewResult(BaseModel):
    """The complete output of a single domain reviewer agent (FR-2.1 through FR-2.6)."""

    domain: ReviewDomain
    score: int = Field(ge=1, le=10)
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    summary: str
    reviewed_at: str


class ScoringGuide(BaseModel):
    """The universal 1-10 scoring anchors (section 13.1), applied per rubric
    dimension so a reviewer has anchored language for each score band."""

    model_config = ConfigDict(populate_by_name=True)

    anchor_1_2: str = Field(alias="1-2", description="Not addressed. No meaningful coverage.")
    anchor_3_4: str = Field(
        alias="3-4", description="Mentioned but inadequate. Critical gaps remain."
    )
    anchor_5_6: str = Field(
        alias="5-6", description="Partially addressed. Lacks depth, specificity, or consistency."
    )
    anchor_7_8: str = Field(alias="7-8", description="Well addressed. Solid coverage with minor gaps.")
    anchor_9_10: str = Field(
        alias="9-10", description="Excellent. Comprehensive, specific, production-ready."
    )


class RubricDimension(BaseModel):
    """A single evaluated dimension within a domain's review rubric (section 13.2-13.6)."""

    name: str
    description: str = Field(
        description="What this dimension evaluates, e.g. 'Auth mechanism, RBAC/ABAC, token lifecycle'."
    )
    scoring_guide: ScoringGuide


class ReviewRubric(BaseModel):
    """The explicit scoring rubric for one review domain, including its weight in the
    overall score (section 13.7) and which org standard categories are routed to it
    (section 5.2 routing table)."""

    domain: ReviewDomain
    org_standard_categories: list[str] = Field(default_factory=list)
    dimensions: list[RubricDimension] = Field(default_factory=list)
    weight: float = Field(
        description="This domain's contribution to the overall weighted score, e.g. 0.25 for architecture."
    )
