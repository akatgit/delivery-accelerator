"""The ProjectContext root schema and its extraction-stage sub-models
(BRD section 12: 12.1 extracted fields, 12.2 review fields, 12.3 generation fields,
12.4 pipeline state fields).

ProjectContext is the single object threaded through the entire pipeline: it starts
as the output of document extraction, accumulates review and QA results, then
generation artifacts, then pipeline state.
"""

from enum import Enum

from pydantic import BaseModel, Field

from backend.schemas.artifacts import AIArtifact, PatternDefinition
from backend.schemas.pipeline import DecisionEntry, FailedComponent, HumanDecision, PipelineStage
from backend.schemas.review import ReviewResult
from backend.schemas.review_qa import ReviewQAResult


class GapSeverity(str, Enum):
    """Severity classification for an extraction gap (FR-1.8)."""

    CRITICAL = "critical"
    """Blocks review."""
    MAJOR = "major"
    """Reviewers will flag it."""
    INFORMATIONAL = "informational"


class TechStackItem(BaseModel):
    """A single technology choice, either declared for the project or detected in an
    existing codebase."""

    category: str
    technology: str
    version: str | None = None
    justification: str | None = None


class Component(BaseModel):
    """A single architectural component extracted from the project documents."""

    name: str
    type: str
    description: str
    tech_stack: list[TechStackItem] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    api_contracts: list[str] = Field(default_factory=list)
    data_entities: list[str] = Field(default_factory=list)


class NFR(BaseModel):
    """A non-functional requirement extracted from the project documents."""

    category: str
    requirement: str
    source: str
    measurable: bool
    notes: str | None = None


class Story(BaseModel):
    """A user story extracted from the project documents."""

    id: str
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    related_components: list[str] = Field(default_factory=list)
    estimated_complexity: str


class Gap(BaseModel):
    """A gap or ambiguity identified in the uploaded documents during extraction (FR-1.8)."""

    description: str
    source_document: str
    severity: GapSeverity
    suggestion: str | None = None


class ExistingCodebase(BaseModel):
    """Structure-only analysis of an optional existing codebase input (FR-1.6)."""

    source: str
    folder_structure: dict | None = None
    detected_stack: list[TechStackItem] = Field(default_factory=list)
    notes: str


class StandardConflict(BaseModel):
    """A detected contradiction between two uploaded org standards (FR-1.5), e.g. a
    naming convention in coding-standards that contradicts naming in api-design."""

    category_a: str
    statement_a: str
    category_b: str
    statement_b: str
    description: str
    resolution: str | None = None
    """Set once the user resolves or acknowledges the conflict."""


class OrgStandards(BaseModel):
    """Organization engineering standards uploaded for the session, routed by
    category (FR-1.3, FR-1.4, section 14)."""

    coding: str | None = None
    security: str | None = None
    api_design: str | None = None
    naming: str | None = None
    logging: str | None = None
    exception_handling: str | None = None
    testing: str | None = None
    cicd: str | None = None
    repository_conventions: str | None = None
    organization_practices: str | None = None
    missing_categories: list[str] = Field(
        default_factory=list,
        description="Expected standard categories that were not uploaded (FR-1.9).",
    )
    conflicts: list[StandardConflict] = Field(default_factory=list)


class ProjectContext(BaseModel):
    """The root object threaded through the entire pipeline (section 12).

    Populated incrementally: extraction fields (12.1) are set by the Document
    Parsing Agent; review fields (12.2) by the Review Board and QA Agent; generation
    fields (12.3) by the AI Development Setup and Scaffolding Agents; pipeline state
    fields (12.4) throughout the run.
    """

    # 12.1 Extracted fields
    project_name: str
    project_description: str
    source_documents: list[str] = Field(default_factory=list)
    org_standards_loaded: list[str] = Field(default_factory=list)

    tech_stack: list[TechStackItem] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    nfrs: list[NFR] = Field(default_factory=list)
    stories: list[Story] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)

    existing_codebase: ExistingCodebase | None = None
    org_standards: OrgStandards = Field(default_factory=OrgStandards)

    # 12.2 Review fields
    reviews: list[ReviewResult] = Field(default_factory=list)
    review_qa: ReviewQAResult | None = None
    overall_score: float | None = None
    remediation_summary: str | None = None

    # 12.3 Generation fields
    patterns: list[PatternDefinition] = Field(default_factory=list)
    ai_artifacts: list[AIArtifact] = Field(default_factory=list)
    scaffolding_structure: dict | None = None

    # 12.4 Pipeline state fields
    current_stage: PipelineStage = PipelineStage.DOCUMENT_PARSING
    review_iteration: int = 0
    failed_components: list[FailedComponent] = Field(default_factory=list)
    human_decisions: list[HumanDecision] = Field(default_factory=list)
    decision_log: list[DecisionEntry] = Field(default_factory=list)
