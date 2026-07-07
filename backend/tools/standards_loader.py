"""Deterministic tool for loading and routing organization engineering standards
(BRD_v2.0.md section 14, FR-1.3, FR-1.4, FR-1.9). No LLM involved.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from backend.schemas.project_context import OrgStandards

logger = logging.getLogger(__name__)

# The ten recognized standard categories (BRD_v2.0.md section 14.1), keyed by the
# OrgStandards field name each populates. Values are keyword tokens that identify
# the category from a filename stem (FR-1.3: "identified by filename or
# subfolder", e.g. security-standards.md, coding-guidelines.md).
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "coding": ["coding", "code"],
    "security": ["security", "secure"],
    "api_design": ["api"],
    "naming": ["naming", "names"],
    "logging": ["logging", "logs", "log"],
    "exception_handling": ["exception", "exceptions"],
    "testing": ["testing", "tests", "test", "qa"],
    "cicd": ["cicd", "ci", "cd"],
    "repository_conventions": ["repository", "repo"],
    "organization_practices": ["organization", "practices", "practice"],
}

ALL_CATEGORIES: tuple[str, ...] = tuple(CATEGORY_KEYWORDS.keys())

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _categorize(filename: str) -> str | None:
    """Match a filename to one of the recognized categories (FR-1.4).

    Returns None for unrecognized files. Per FR-1.4 those are still accepted by
    the upload flow, just classified as "general" standards -- i.e. loaded but
    not routed to any specific reviewer or artifact section.
    """
    stem = Path(filename).stem.lower()
    tokens = set(_TOKEN_RE.findall(stem))
    for category, keywords in CATEGORY_KEYWORDS.items():
        if tokens & set(keywords):
            return category
    return None


def load_standards(directory: str | Path) -> OrgStandards:
    """Read every standards file in ``directory``, categorize it by filename
    (FR-1.4), and populate ``missing_categories`` for any of the ten recognized
    categories that had no matching file (FR-1.9).

    Conflicts between standards are not detected here -- that's the job of the
    ``detect-standard-conflicts`` LLM skill (ARCHITECTURE_v2.0.md section 4.4).
    """
    directory = Path(directory)
    found: dict[str, str] = {}

    if not directory.is_dir():
        logger.warning("Standards directory does not exist: %s", directory)
    else:
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue

            category = _categorize(path.name)
            if category is None:
                logger.info("Unrecognized standards file '%s' classified as general", path.name)
                continue

            content = path.read_text(encoding="utf-8").strip()
            if not content:
                logger.warning("Standards file '%s' is empty; skipping", path.name)
                continue

            if category in found:
                logger.warning(
                    "Multiple files matched category '%s'; '%s' overwrites the previous match",
                    category,
                    path.name,
                )
            found[category] = content

    missing = [category for category in ALL_CATEGORIES if category not in found]
    if missing:
        logger.info("Missing standard categories: %s", missing)

    return OrgStandards(missing_categories=missing, **found)


def route_standards(org_standards: OrgStandards, target_categories: list[str]) -> str:
    """Concatenate the content of the given org standard categories into a
    single string with category headers (BRD_v2.0.md section 14.2 routing
    table), ready to hand to an LLM skill or reviewer prompt.

    Unknown category names are logged and skipped; categories with no content
    (not uploaded) are silently skipped.
    """
    sections = []
    for category in target_categories:
        if category not in ALL_CATEGORIES:
            logger.warning("route_standards: '%s' is not a recognized OrgStandards category", category)
            continue
        content = getattr(org_standards, category, None)
        if content:
            sections.append(f"## {category}\n{content}")
    return "\n\n".join(sections)
