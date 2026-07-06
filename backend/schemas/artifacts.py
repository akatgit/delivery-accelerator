"""Generation-stage schemas for architectural patterns and AI development artifacts
(BRD section 12.3, FR-4, FR-5)."""

from pydantic import BaseModel, Field


class PatternDefinition(BaseModel):
    """An architectural pattern identified for the project, generated with a sample
    implementation, test file, and usage header (FR-5.3)."""

    name: str
    description: str
    applicable_components: list[str] = Field(default_factory=list)
    template_path: str
    ai_skill_ref: str | None = None


class AIArtifact(BaseModel):
    """A single generated AI development artifact (e.g. instructions.md, a skill file,
    a hook config, a tool-specific config) produced by a skill invocation (FR-4.4, FR-4.5)."""

    type: str
    filename: str
    content: str
    derived_from: list[str] = Field(
        default_factory=list,
        description="ProjectContext refs (findings, standards, decisions) that informed this artifact.",
    )
    used_default: bool = Field(
        description="True if generated from LLM best practices because no org standard was provided (FR-4.3)."
    )
    prompt_version: str = Field(
        description="Version of the prompt template used, for traceability back to the exact prompt (FR-4.5)."
    )
