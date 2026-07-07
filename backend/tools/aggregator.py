"""Review Aggregator (ARCHITECTURE_v2.0.md section 5.3; FR-2.6 through FR-2.9).

A deterministic tool -- no LLM. Merges findings from all completed reviewers,
sorts them by severity, computes the overall weighted score (redistributing a
failed domain's weight across the domains that did report), and generates a
remediation summary.
"""

from __future__ import annotations

from backend.rubrics.loader import load_rubric
from backend.schemas.review import Finding, ReviewResult, Severity

PASSING_THRESHOLD = 6.0
"""Minimum overall score required to proceed to generation (FR-2.8)."""

_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.MAJOR: 1,
    Severity.MINOR: 2,
    Severity.SUGGESTION: 3,
}


def aggregate_reviews(reviews: list[ReviewResult], failed_domains: list[str]) -> dict:
    """Merge, score, and summarize a set of completed domain reviews.

    `failed_domains` lists the `ReviewDomain` values (as strings) that produced
    no `ReviewResult` at all -- e.g. a reviewer agent crashed outright, as
    opposed to a reviewer that ran and just scored some dimensions (that still
    produces a `ReviewResult`, just a lower-confidence one; BaseReviewer
    already degrades gracefully at the dimension level). Any review whose
    domain also appears in `failed_domains` is defensively excluded too, in
    case a caller passes inconsistent data.

    Returns a dict with:
    - `findings`: every finding across all active reviews, sorted by severity
      (critical first), with domain then finding id as tiebreakers for
      deterministic output regardless of the order `reviews` arrived in (the
      five reviewers run in parallel, so that order isn't guaranteed).
    - `overall_score`: the weighted score across active domains only, using
      each domain's rubric weight (section 13.7), renormalized so the
      failed domains' weight is redistributed across the rest (FR-2.7,
      FR-2.9). `None` if no domain reviews are active.
    - `remediation_summary`: a short human-readable summary of what was
      aggregated, what failed, and the finding breakdown by severity.
    - `threshold_passed`: `True` if `overall_score >= PASSING_THRESHOLD`
      (FR-2.8), else `False`.
    """
    failed_set = set(failed_domains)
    active_reviews = [r for r in reviews if r.domain.value not in failed_set]

    findings = _merge_findings(active_reviews)
    overall_score = _compute_weighted_score(active_reviews)
    remediation_summary = _build_remediation_summary(active_reviews, failed_domains, findings)
    threshold_passed = overall_score is not None and overall_score >= PASSING_THRESHOLD

    return {
        "findings": findings,
        "overall_score": overall_score,
        "remediation_summary": remediation_summary,
        "threshold_passed": threshold_passed,
    }


def _merge_findings(reviews: list[ReviewResult]) -> list[Finding]:
    # Findings don't carry their originating domain, so tag each with its
    # review's domain here purely for a deterministic sort tiebreaker --
    # `reviews` arrives in whatever order the five parallel reviewers
    # completed in, which isn't guaranteed to be the same across runs.
    tagged = [
        (review.domain.value, finding) for review in reviews for finding in review.findings
    ]
    tagged.sort(key=lambda pair: (_SEVERITY_ORDER[pair[1].severity], pair[0], pair[1].id))
    return [finding for _, finding in tagged]


def _compute_weighted_score(reviews: list[ReviewResult]) -> float | None:
    if not reviews:
        return None
    weighted_sum = 0.0
    total_weight = 0.0
    for review in reviews:
        rubric = load_rubric(review.domain)
        weighted_sum += review.score * rubric.weight
        total_weight += rubric.weight
    return round(weighted_sum / total_weight, 2) if total_weight else None


def _build_remediation_summary(
    reviews: list[ReviewResult], failed_domains: list[str], findings: list[Finding]
) -> str:
    if not reviews:
        return "No domain reviews completed; unable to generate a remediation summary."

    parts = []
    domain_names = ", ".join(sorted(review.domain.value for review in reviews))
    parts.append(f"Aggregated {len(reviews)} domain review(s): {domain_names}.")

    if failed_domains:
        parts.append(
            f"{len(failed_domains)} domain(s) failed and were excluded from the score, "
            f"with their weight redistributed across the remaining domains: "
            f"{', '.join(sorted(failed_domains))}."
        )

    severity_counts = {severity: 0 for severity in Severity}
    for finding in findings:
        severity_counts[finding.severity] += 1
    parts.append(
        f"{len(findings)} finding(s): {severity_counts[Severity.CRITICAL]} critical, "
        f"{severity_counts[Severity.MAJOR]} major, {severity_counts[Severity.MINOR]} minor, "
        f"{severity_counts[Severity.SUGGESTION]} suggestion."
    )

    return " ".join(parts)
