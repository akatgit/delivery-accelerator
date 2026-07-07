"""Consistency Checker (ARCHITECTURE_v2.0.md section 5.8). A deterministic
tool -- no LLM. Validates generated AIArtifacts against each other and
against org_standards, flagging non-blocking inconsistency warnings.

Three checks, matching section 5.8's own wording:
1. "naming conventions in skills match instructions.md" -- each skill file's
   underlying pattern should be mentioned in instructions.md.
2. "hook lint rules align with coding standards" -- generalized to every
   artifact: an artifact's `used_default` flag must agree with whether its
   referenced standard(s) are actually present in org_standards.
3. "PR template items trace to review rubric" -- a PR-template hook config
   should reference at least one of the five review domains.
"""

from __future__ import annotations

from backend.schemas.artifacts import AIArtifact
from backend.schemas.project_context import OrgStandards

REVIEW_DOMAINS = ["architecture", "security", "performance", "reliability", "compliance"]


def check_consistency(artifacts: list[AIArtifact], org_standards: OrgStandards) -> list[str]:
    """Runs all consistency checks and returns the combined list of
    non-blocking warnings."""
    warnings: list[str] = []
    warnings.extend(_check_used_default_matches_standard_presence(artifacts, org_standards))
    warnings.extend(_check_skill_naming_matches_instructions(artifacts))
    warnings.extend(_check_pr_template_traces_to_rubric(artifacts))
    return warnings


def _standard_refs(artifact: AIArtifact) -> list[str]:
    return [ref.split("standard:", 1)[1] for ref in artifact.derived_from if ref.startswith("standard:")]


def _check_used_default_matches_standard_presence(
    artifacts: list[AIArtifact], org_standards: OrgStandards
) -> list[str]:
    warnings = []
    for artifact in artifacts:
        for category in _standard_refs(artifact):
            present = bool(getattr(org_standards, category, None))
            if artifact.used_default and present:
                warnings.append(
                    f"{artifact.filename}: marked used_default=True but references standard "
                    f"'{category}', which IS provided -- the artifact may not actually reflect it."
                )
            elif not artifact.used_default and not present:
                warnings.append(
                    f"{artifact.filename}: claims to follow standard '{category}', but no "
                    f"'{category}' standard was provided."
                )
    return warnings


def _check_skill_naming_matches_instructions(artifacts: list[AIArtifact]) -> list[str]:
    instructions = next((a for a in artifacts if a.type == "instructions_md"), None)
    if instructions is None:
        return []

    warnings = []
    instructions_content_lower = instructions.content.lower()
    for artifact in artifacts:
        if artifact.type != "skill_file":
            continue
        pattern_names = [ref.split("pattern:", 1)[1] for ref in artifact.derived_from if ref.startswith("pattern:")]
        for pattern_name in pattern_names:
            if pattern_name.lower() not in instructions_content_lower:
                warnings.append(
                    f"{artifact.filename}: pattern '{pattern_name}' is not mentioned anywhere in "
                    "instructions.md; skill naming should trace back to the conventions doc."
                )
    return warnings


def _check_pr_template_traces_to_rubric(artifacts: list[AIArtifact]) -> list[str]:
    warnings = []
    for artifact in artifacts:
        if artifact.type != "hook_config":
            continue
        filename_lower = artifact.filename.lower()
        if "pr-template" not in filename_lower and "pr template" not in filename_lower:
            continue
        content_lower = artifact.content.lower()
        if not any(domain in content_lower for domain in REVIEW_DOMAINS):
            warnings.append(
                f"{artifact.filename}: PR template doesn't reference any review domain "
                f"({', '.join(REVIEW_DOMAINS)}); checklist items should trace to the review rubric."
            )
    return warnings
