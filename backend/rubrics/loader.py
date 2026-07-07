"""Deterministic loader for review rubric YAML files (ARCHITECTURE_v2.0.md
section 5.2, 14 — a Tool: no LLM involved)."""

from pathlib import Path

import yaml

from backend.schemas.review import ReviewDomain, ReviewRubric

RUBRICS_DIR = Path(__file__).resolve().parent


def load_rubric(domain: ReviewDomain) -> ReviewRubric:
    """Load and validate ``{domain}.yaml`` from the rubrics directory into a
    ``ReviewRubric``."""
    path = RUBRICS_DIR / f"{domain.value}.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ReviewRubric.model_validate(data)
