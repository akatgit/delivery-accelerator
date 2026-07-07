"""Placeholder node functions for every step of the pipeline graph
(ARCHITECTURE_v2.0.md section 9.1).

Each function is a stand-in for the real agent/tool described in section 5. They
exist so the graph in ``backend/graph/pipeline.py`` compiles and can be exercised
end to end before the real agents (``backend/agents/...``) are wired in. Every
placeholder returns a partial state update (a dict of the fields it changed) rather
than the full state, which is what LangGraph expects from a node function and is
required for the parallel reviewer nodes to merge correctly via the reducers
defined in ``backend/graph/state.py``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.types import interrupt

from backend.agents.ai_setup import AIDevSetupAgent
from backend.agents.context_synthesizer import ContextSynthesizerAgent
from backend.agents.document_parser import DocumentParsingAgent
from backend.agents.review_qa import ReviewQAAgent
from backend.agents.reviewers.architecture import ArchitectureReviewer
from backend.agents.reviewers.base_reviewer import BaseReviewer
from backend.agents.reviewers.compliance import ComplianceReviewer
from backend.agents.reviewers.performance import PerformanceReviewer
from backend.agents.reviewers.reliability import ReliabilityReviewer
from backend.agents.reviewers.security import SecurityReviewer
from backend.agents.scaffolder import ProjectScaffolderAgent
from backend.config import settings
from backend.graph.state import PipelineState
from backend.schemas.pipeline import DecisionEntry, HumanDecision, HumanDecisionAction, PipelineStage
from backend.schemas.review import Finding, FindingStatus, ReviewDomain, Severity
from backend.tools.aggregator import PASSING_THRESHOLD
from backend.tools.aggregator import aggregate_reviews as run_aggregator
from backend.tools.consistency_checker import check_consistency
from backend.tools.zip_builder import build_zip as build_zip_tool

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Document parsing (ARCHITECTURE_v2.0.md section 5.1)
# ----------------------------------------------------------------------

_document_parsing_agent: DocumentParsingAgent | None = None


def _get_document_parsing_agent() -> DocumentParsingAgent:
    """Lazily construct (and cache) the real DocumentParsingAgent. Constructing
    it builds 6 skills, each of which loads a prompt template from disk and
    (for structured-output skills) binds an LLM client, so it's built once and
    reused rather than per node invocation. Tests can monkeypatch this
    function, or set the module-level `_document_parsing_agent` directly, to
    inject an agent built with fake-LLM-backed skills."""
    global _document_parsing_agent
    if _document_parsing_agent is None:
        _document_parsing_agent = DocumentParsingAgent()
    return _document_parsing_agent


def parse_documents(state: PipelineState) -> dict:
    """Runs the Document Parsing Agent (ARCHITECTURE_v2.0.md section 5.1):
    loads and categorizes org standards, detects conflicts between them, then
    extracts tech stack, components, NFRs, stories, and gaps in sequence.

    `DocumentParsingAgent.run()` mutates `state` in place and returns the whole
    object -- fine for a solitary sequential node like this one, except that
    `failed_components` and `decision_log` carry LangGraph reducers
    (`operator.add`, see `graph/state.py`). Returning their *entire*
    accumulated value as this node's output would get concatenated onto
    whatever's already in the channel, duplicating every prior entry (e.g. on
    a revise loop, where this node runs again with prior history already
    present). We snapshot how many entries existed before this node ran and
    return only the newly appended slice for those two fields.
    `reviews` isn't touched here at all, so it's simply omitted from the update.
    """
    decision_log_before = len(state.decision_log)
    failed_components_before = len(state.failed_components)

    agent = _get_document_parsing_agent()
    updated = agent.run(state)

    logger.info(
        "parse_documents: extracted %d component(s), %d NFR(s), %d stor(y/ies), %d gap(s) "
        "(iteration %d)",
        len(updated.components),
        len(updated.nfrs),
        len(updated.stories),
        len(updated.gaps),
        updated.review_iteration,
    )

    return {
        "org_standards": updated.org_standards,
        "tech_stack": updated.tech_stack,
        "components": updated.components,
        "nfrs": updated.nfrs,
        "stories": updated.stories,
        "gaps": updated.gaps,
        "current_stage": PipelineStage.EXTRACTION_PREVIEW,
        "decision_log": updated.decision_log[decision_log_before:],
        "failed_components": updated.failed_components[failed_components_before:],
    }


def detect_standard_conflicts(state: PipelineState) -> dict:
    """Checks the org-standard conflicts already detected by the Document
    Parsing Agent's detect-standard-conflicts skill (ARCHITECTURE_v2.0.md
    section 4.4), which runs as part of `parse_documents` above. Conflicts are
    surfaced to the user and resolved/acknowledged before the pipeline starts
    (FR-1.5), so by the time this node runs it's just a checkpoint."""
    logger.info(
        "detect_standard_conflicts: %d conflict(s) currently on record",
        len(state.org_standards.conflicts),
    )
    return {"current_stage": PipelineStage.REVIEW_BOARD}


# ----------------------------------------------------------------------
# Review board — five parallel reviewers (ARCHITECTURE_v2.0.md section 5.2)
# ----------------------------------------------------------------------


_reviewer_agents: dict[str, BaseReviewer] = {}

_REVIEWER_CLASSES: dict[str, type[BaseReviewer]] = {
    "architecture_reviewer": ArchitectureReviewer,
    "security_reviewer": SecurityReviewer,
    "performance_reviewer": PerformanceReviewer,
    "reliability_reviewer": ReliabilityReviewer,
    "compliance_reviewer": ComplianceReviewer,
}


def _get_reviewer(node_name: str) -> BaseReviewer:
    """Lazily construct (and cache) a reviewer agent. Constructing one builds
    its evaluate-dimension skill (loads the prompt template, binds an LLM
    client) and loads its rubric YAML, so it's built once and reused rather
    than per node invocation. Tests can set `_reviewer_agents[node_name]`
    directly to inject a reviewer built with fake-LLM-backed skills."""
    if node_name not in _reviewer_agents:
        _reviewer_agents[node_name] = _REVIEWER_CLASSES[node_name]()
    return _reviewer_agents[node_name]


def _run_reviewer(state: PipelineState, node_name: str) -> dict:
    """Runs a reviewer agent and returns only the delta it produced.

    `BaseReviewer.run()` mutates `state` in place and returns the whole
    object. `reviews`, `decision_log`, and `failed_components` all carry
    LangGraph reducers (`operator.add`, see `graph/state.py`), and this node
    is one of five parallel branches fanned out via `Send()`
    (`route_to_reviewers` in `graph/pipeline.py`) -- returning the *entire*
    accumulated value of any of them would get concatenated onto whatever the
    channel already holds (duplicating prior history, e.g. across a revise
    loop) and would collide with the other four branches' updates to the same
    fields in the same superstep. Each branch instead reports only the slice
    it personally added. `route_to_reviewers` also gives each branch its own
    deep copy of `state`, so these before/after snapshots are never disturbed
    by the other four branches running concurrently.
    """
    reviews_before = len(state.reviews)
    decision_log_before = len(state.decision_log)
    failed_before = len(state.failed_components)

    reviewer = _get_reviewer(node_name)
    updated = reviewer.run(state)

    return {
        "reviews": updated.reviews[reviews_before:],
        "decision_log": updated.decision_log[decision_log_before:],
        "failed_components": updated.failed_components[failed_before:],
    }


def architecture_reviewer(state: PipelineState) -> dict:
    """Runs the ArchitectureReviewer (ARCHITECTURE_v2.0.md section 5.2)."""
    return _run_reviewer(state, "architecture_reviewer")


def security_reviewer(state: PipelineState) -> dict:
    """Runs the SecurityReviewer (ARCHITECTURE_v2.0.md section 5.2)."""
    return _run_reviewer(state, "security_reviewer")


def performance_reviewer(state: PipelineState) -> dict:
    """Runs the PerformanceReviewer (ARCHITECTURE_v2.0.md section 5.2)."""
    return _run_reviewer(state, "performance_reviewer")


def reliability_reviewer(state: PipelineState) -> dict:
    """Runs the ReliabilityReviewer (ARCHITECTURE_v2.0.md section 5.2)."""
    return _run_reviewer(state, "reliability_reviewer")


def compliance_reviewer(state: PipelineState) -> dict:
    """Runs the ComplianceReviewer (ARCHITECTURE_v2.0.md section 5.2)."""
    return _run_reviewer(state, "compliance_reviewer")


# ----------------------------------------------------------------------
# Aggregation and QA (ARCHITECTURE_v2.0.md sections 5.3, 5.4)
# ----------------------------------------------------------------------


def aggregate_reviews(state: PipelineState) -> dict:
    """Runs the Review Aggregator tool (ARCHITECTURE_v2.0.md section 5.3):
    deterministic merge, severity-sorted findings, weighted overall score
    (excluding any domain that failed to produce a review, redistributing its
    weight across the rest), and a remediation summary.

    `run_aggregator()` returns a richer dict (`findings`, `overall_score`,
    `remediation_summary`, `threshold_passed`) than `PipelineState` has fields
    for -- there's no top-level "merged findings" or "threshold_passed" field
    on `ProjectContext` (section 12), since those are presentation-layer
    concerns (FR-3.1: shown to the human at the approval gate) recomputable
    on demand from `state.reviews`, not pipeline state to persist. Only
    `overall_score` and `remediation_summary` map onto real state fields.
    """
    failed_domains = [domain.value for domain in ReviewDomain if domain not in _reviewed_domains(state)]
    result = run_aggregator(state.reviews, failed_domains)

    logger.info(
        "aggregate_reviews: overall_score=%s (threshold_passed=%s) from %d/%d domain(s), "
        "%d finding(s), failed=%s",
        result["overall_score"],
        result["threshold_passed"],
        len(state.reviews),
        len(ReviewDomain),
        len(result["findings"]),
        failed_domains,
    )
    return {
        "overall_score": result["overall_score"],
        "remediation_summary": result["remediation_summary"],
        "current_stage": PipelineStage.REVIEW_AGGREGATION,
    }


def _reviewed_domains(state: PipelineState) -> set[ReviewDomain]:
    return {review.domain for review in state.reviews}


_review_qa_agent: ReviewQAAgent | None = None


def _get_review_qa_agent() -> ReviewQAAgent:
    """Lazily construct (and cache) the real ReviewQAAgent. Tests can set the
    module-level `_review_qa_agent` directly to inject fake-LLM-backed skills."""
    global _review_qa_agent
    if _review_qa_agent is None:
        _review_qa_agent = ReviewQAAgent()
    return _review_qa_agent


def review_qa(state: PipelineState) -> dict:
    """Runs the Review QA Agent (ARCHITECTURE_v2.0.md section 5.4): invokes
    deduplicate-findings, detect-contradictions, validate-actionability, and
    check-coverage, then merges duplicate findings, normalizes severities, and
    computes a quality score.

    `ReviewQAAgent.run()` mutates existing `Finding` objects nested inside
    `state.reviews` (setting `duplicate_of`/`contributing_domains`) rather than
    adding new `ReviewResult` entries. Returning the whole updated `reviews`
    list is safe here because its reducer (`_merge_reviews`, `graph/state.py`)
    replaces each domain's existing entry rather than blindly appending --
    unlike `decision_log`/`failed_components`, which are pure append-only
    audit logs and still need the before/after slicing used elsewhere in this
    module.
    """
    decision_log_before = len(state.decision_log)
    failed_components_before = len(state.failed_components)

    agent = _get_review_qa_agent()
    updated = agent.run(state)

    logger.info(
        "review_qa: quality_score=%s, %d duplicate(s), %d contradiction(s)",
        updated.review_qa.quality_score if updated.review_qa else None,
        updated.review_qa.duplicates_found if updated.review_qa else 0,
        len(updated.review_qa.contradictions) if updated.review_qa else 0,
    )

    return {
        "review_qa": updated.review_qa,
        "reviews": updated.reviews,
        "current_stage": PipelineStage.REVIEW_QA,
        "decision_log": updated.decision_log[decision_log_before:],
        "failed_components": updated.failed_components[failed_components_before:],
    }


# ----------------------------------------------------------------------
# Human approval gate 1 (ARCHITECTURE_v2.0.md section 5.5)
# ----------------------------------------------------------------------


MIN_JUSTIFICATION_LENGTH = 20
"""Minimum length for an override or contradiction-resolution justification (FR-3.3)."""

MAX_REVIEW_ITERATIONS = 5
"""Maximum review-revise iterations per session (FR-3.9)."""


class GateValidationError(Exception):
    """Raised when a human_gate_1 resume payload fails validation. The node
    catches this and re-interrupts with an error message rather than crashing
    the graph run, so the caller can correct and resubmit."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_finding(state: PipelineState, finding_id: str) -> Finding | None:
    for review in state.reviews:
        for finding in review.findings:
            if finding.id == finding_id:
                return finding
    return None


def _findings_for_domain(state: PipelineState, domain: str) -> list[Finding]:
    return [
        finding
        for review in state.reviews
        if review.domain.value == domain
        for finding in review.findings
        if finding.duplicate_of is None
    ]


def _record_human_decision(state: PipelineState, decision: HumanDecision, *, gate_name: str = "human_gate_1") -> None:
    """Appends to both `human_decisions` (FR-3.8's own record) and the
    unified `decision_log` (every agent/skill/human decision, section 12.4)."""
    state.human_decisions.append(decision)
    state.decision_log.append(
        DecisionEntry(
            timestamp=decision.timestamp,
            agent=gate_name,
            skill=None,
            prompt_version=None,
            decision=f"{decision.action.value}" + (f" ({decision.domain})" if decision.domain else ""),
            rationale=decision.justification or "(no justification provided)",
            alternatives_considered=[],
            context_refs=decision.finding_ids,
            standard_refs=[],
        )
    )


def _build_gate_1_payload(state: PipelineState) -> dict:
    """Everything FR-3.1 requires showing the human: overall score, review
    quality score, all findings grouped by severity (deduplicated -- findings
    already merged away by review_qa are omitted), contradictions, and the
    minimum score threshold status."""
    findings_by_severity: dict[str, list[dict]] = {severity.value: [] for severity in Severity}
    for review in state.reviews:
        for finding in review.findings:
            if finding.duplicate_of is not None:
                continue
            findings_by_severity[finding.severity.value].append(
                {
                    "id": finding.id,
                    "title": finding.title,
                    "affected_components": finding.affected_components,
                    "contributing_domains": finding.contributing_domains,
                    "status": finding.status.value,
                }
            )

    contradictions = state.review_qa.contradictions if state.review_qa else []
    return {
        "stage": "human_gate_1",
        "overall_score": state.overall_score,
        "threshold_passed": state.overall_score is not None and state.overall_score >= PASSING_THRESHOLD,
        "review_quality_score": state.review_qa.quality_score if state.review_qa else None,
        "findings_by_severity": findings_by_severity,
        "contradictions": [c.model_dump(mode="json") for c in contradictions],
        "remediation_summary": state.remediation_summary,
        "review_iteration": state.review_iteration,
    }


def _parse_action(resume_value) -> HumanDecisionAction:
    if not isinstance(resume_value, dict) or "decision" not in resume_value:
        raise GateValidationError("Resume payload must be a dict with a 'decision' key.")
    try:
        return HumanDecisionAction(resume_value["decision"])
    except ValueError:
        raise GateValidationError(
            f"Unknown decision '{resume_value.get('decision')}'. "
            f"Expected one of: {[action.value for action in HumanDecisionAction]}."
        )


def _apply_accept(state: PipelineState) -> None:
    """FR-3.2: accept all findings as acknowledged."""
    accepted_ids = []
    for review in state.reviews:
        for finding in review.findings:
            if finding.duplicate_of is not None:
                continue
            finding.status = FindingStatus.ACCEPTED
            accepted_ids.append(finding.id)

    _record_human_decision(
        state,
        HumanDecision(
            timestamp=_now(), action=HumanDecisionAction.ACCEPT,
            finding_ids=accepted_ids, justification=None, domain=None,
        ),
    )


def _apply_override(state: PipelineState, overrides: list[dict]) -> None:
    """FR-3.3 (per finding) and FR-3.4 (per domain): override specific
    findings or whole domains, each with a >= 20 character justification and,
    for critical findings, explicit confirmation. Any finding not explicitly
    overridden is implicitly accepted (FR-3.7). All entries are validated
    before any mutation is applied, so a single bad entry can't leave a
    partial override applied.
    """
    if not overrides:
        raise GateValidationError("'override' decision requires at least one entry in 'overrides'.")

    resolved: list[tuple[list[Finding], str, str | None]] = []
    for entry in overrides:
        justification = entry.get("justification", "")
        if len(justification) < MIN_JUSTIFICATION_LENGTH:
            raise GateValidationError(
                f"Override justification must be at least {MIN_JUSTIFICATION_LENGTH} characters "
                f"(got {len(justification)}): {entry}"
            )

        if "domain" in entry:
            findings = _findings_for_domain(state, entry["domain"])
            if not findings:
                raise GateValidationError(f"No findings found for domain '{entry['domain']}'.")
        elif "finding_id" in entry:
            finding = _find_finding(state, entry["finding_id"])
            if finding is None:
                raise GateValidationError(f"No finding found with id '{entry['finding_id']}'.")
            findings = [finding]
        else:
            raise GateValidationError(f"Override entry must include 'finding_id' or 'domain': {entry}")

        critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
        if critical_findings and not entry.get("confirmed", False):
            raise GateValidationError(
                f"Overriding critical finding(s) {[f.id for f in critical_findings]} "
                "requires 'confirmed': true."
            )

        resolved.append((findings, justification, entry.get("domain")))

    overridden_ids: set[str] = set()
    for findings, justification, domain in resolved:
        for finding in findings:
            finding.status = FindingStatus.OVERRIDDEN
            finding.override_justification = justification
            overridden_ids.add(finding.id)
        _record_human_decision(
            state,
            HumanDecision(
                timestamp=_now(), action=HumanDecisionAction.OVERRIDE,
                finding_ids=[f.id for f in findings], justification=justification, domain=domain,
            ),
        )

    accepted_ids = []
    for review in state.reviews:
        for finding in review.findings:
            if finding.duplicate_of is not None or finding.id in overridden_ids:
                continue
            finding.status = FindingStatus.ACCEPTED
            accepted_ids.append(finding.id)
    if accepted_ids:
        _record_human_decision(
            state,
            HumanDecision(
                timestamp=_now(), action=HumanDecisionAction.ACCEPT,
                finding_ids=accepted_ids, justification=None, domain=None,
            ),
        )


def _apply_revise(state: PipelineState, justification: str | None) -> None:
    """FR-3.5 / FR-3.9: send back for revision, incrementing review_iteration
    up to a maximum of 5.

    FR-3.5 also says only reviewers whose domains had open major/critical
    findings should be re-run on revise (minor/suggestion findings carry
    forward). That selective re-run isn't implemented here -- `route_to_reviewers`
    (graph/pipeline.py) always fans out to all five reviewers unconditionally;
    this only handles the iteration counter and the decision record.
    """
    if state.review_iteration >= MAX_REVIEW_ITERATIONS:
        raise GateValidationError(
            f"Maximum of {MAX_REVIEW_ITERATIONS} review-revise iterations reached; "
            "please accept or override instead of revising again."
        )
    state.review_iteration += 1
    _record_human_decision(
        state,
        HumanDecision(
            timestamp=_now(), action=HumanDecisionAction.REVISE,
            finding_ids=[], justification=justification, domain=None,
        ),
    )


def _apply_contradiction_resolutions(state: PipelineState, resolutions: list[dict]) -> None:
    """FR-3.6: for each contradiction, the human explicitly chooses which
    recommendation to follow; the unchosen one is marked resolved with the
    human's rationale. All entries are validated before any mutation is
    applied, for the same atomicity reason as `_apply_override`."""
    if not resolutions:
        raise GateValidationError(
            "'resolve_contradiction' decision requires at least one entry in 'contradiction_resolutions'."
        )
    if state.review_qa is None or not state.review_qa.contradictions:
        raise GateValidationError("No contradictions available to resolve.")

    contradictions_by_pair = {
        (c.finding_id_a, c.finding_id_b): c for c in state.review_qa.contradictions
    }

    resolved: list[tuple] = []
    for entry in resolutions:
        id_a = entry.get("finding_id_a")
        id_b = entry.get("finding_id_b")
        chosen = entry.get("chosen_finding_id")
        rationale = entry.get("rationale", "")

        contradiction = contradictions_by_pair.get((id_a, id_b)) or contradictions_by_pair.get((id_b, id_a))
        if contradiction is None:
            raise GateValidationError(f"No contradiction found for finding pair ({id_a!r}, {id_b!r}).")
        if chosen not in (id_a, id_b):
            raise GateValidationError(
                f"'chosen_finding_id' must be one of {id_a!r} or {id_b!r}, got {chosen!r}."
            )
        if len(rationale) < MIN_JUSTIFICATION_LENGTH:
            raise GateValidationError(
                f"Contradiction resolution rationale must be at least {MIN_JUSTIFICATION_LENGTH} "
                f"characters (got {len(rationale)})."
            )

        unchosen_id = id_b if chosen == id_a else id_a
        resolved.append((contradiction, id_a, id_b, chosen, unchosen_id, rationale))

    for contradiction, id_a, id_b, chosen, unchosen_id, rationale in resolved:
        unchosen_finding = _find_finding(state, unchosen_id)
        if unchosen_finding is not None:
            unchosen_finding.status = FindingStatus.RESOLVED
            unchosen_finding.override_justification = f"resolved — alternative chosen: {rationale}"
        contradiction.resolution = f"Chose {chosen} over {unchosen_id}: {rationale}"

        _record_human_decision(
            state,
            HumanDecision(
                timestamp=_now(), action=HumanDecisionAction.RESOLVE_CONTRADICTION,
                finding_ids=[id_a, id_b], justification=rationale, domain=None,
            ),
        )


def human_gate_1(state: PipelineState) -> dict:
    """First human approval gate (ARCHITECTURE_v2.0.md section 5.5;
    BRD_v2.0.md FR-3). Uses LangGraph's dynamic `interrupt()` rather than
    `interrupt_before`: the graph pauses *inside* this node, and each call to
    `interrupt()` returns whatever value the caller supplies via
    `graph.invoke(Command(resume=...), config=...)`.

    The node loops on `interrupt()`: a "resolve_contradiction" decision is
    processed and the loop re-prompts (there can be several -- one per
    contradiction -- before the human gives a final verdict); an invalid
    resume payload re-prompts with an error message rather than crashing the
    run; only a terminal "accept", "override", or "revise" decision ends the
    loop and lets the graph proceed to `route_after_human_gate_1`
    (`graph/pipeline.py`).
    """
    decision_log_before = len(state.decision_log)
    payload = _build_gate_1_payload(state)

    while True:
        resume_value = interrupt(payload)
        try:
            action = _parse_action(resume_value)
            if action == HumanDecisionAction.RESOLVE_CONTRADICTION:
                _apply_contradiction_resolutions(state, resume_value.get("contradiction_resolutions", []))
                payload = _build_gate_1_payload(state)
                continue
            if action == HumanDecisionAction.ACCEPT:
                _apply_accept(state)
            elif action == HumanDecisionAction.OVERRIDE:
                _apply_override(state, resume_value.get("overrides", []))
            elif action == HumanDecisionAction.REVISE:
                _apply_revise(state, resume_value.get("justification"))
            else:
                raise GateValidationError(f"Unhandled decision '{action}'.")
        except GateValidationError as exc:
            logger.warning("human_gate_1: rejecting resume payload: %s", exc)
            payload = {**payload, "error": str(exc)}
            continue
        break

    logger.info(
        "human_gate_1: resolved with %d total human decision(s) recorded so far",
        len(state.human_decisions),
    )
    return {
        "reviews": state.reviews,
        "review_qa": state.review_qa,
        "human_decisions": state.human_decisions,
        "review_iteration": state.review_iteration,
        "current_stage": PipelineStage.HUMAN_APPROVAL_REVIEW,
        "decision_log": state.decision_log[decision_log_before:],
    }


# ----------------------------------------------------------------------
# Generation (ARCHITECTURE_v2.0.md sections 5.6 - 5.9)
# ----------------------------------------------------------------------


_context_synthesizer_agent: ContextSynthesizerAgent | None = None


def _get_context_synthesizer_agent() -> ContextSynthesizerAgent:
    """Lazily construct (and cache) the real ContextSynthesizerAgent. Tests
    can set the module-level `_context_synthesizer_agent` directly to inject
    fake-LLM-backed skills."""
    global _context_synthesizer_agent
    if _context_synthesizer_agent is None:
        _context_synthesizer_agent = ContextSynthesizerAgent()
    return _context_synthesizer_agent


def synthesize_context(state: PipelineState) -> dict:
    """Runs the Context Synthesis Agent (ARCHITECTURE_v2.0.md section 5.6):
    identifies needed patterns and plans artifact generation, both informed
    only by approved context (FR-4.2) -- overridden findings and the
    unchosen side of a resolved contradiction never reach either skill."""
    decision_log_before = len(state.decision_log)
    failed_components_before = len(state.failed_components)

    agent = _get_context_synthesizer_agent()
    updated = agent.run(state)

    logger.info(
        "synthesize_context: %d pattern(s) identified, generation_plan %s",
        len(updated.patterns),
        "set" if updated.generation_plan else "not set",
    )

    return {
        "patterns": updated.patterns,
        "generation_plan": updated.generation_plan,
        "current_stage": PipelineStage.CONTEXT_SYNTHESIS,
        "decision_log": updated.decision_log[decision_log_before:],
        "failed_components": updated.failed_components[failed_components_before:],
    }


_ai_dev_setup_agent: AIDevSetupAgent | None = None


def _get_ai_dev_setup_agent() -> AIDevSetupAgent:
    """Lazily construct (and cache) the real AIDevSetupAgent. Tests can set
    the module-level `_ai_dev_setup_agent` directly to inject fake-LLM-backed
    skills."""
    global _ai_dev_setup_agent
    if _ai_dev_setup_agent is None:
        _ai_dev_setup_agent = AIDevSetupAgent()
    return _ai_dev_setup_agent


def generate_ai_artifacts(state: PipelineState) -> dict:
    """Runs the AI Development Setup Agent (ARCHITECTURE_v2.0.md section 5.7):
    generates instructions.md, skill files, hook configs, prompt library
    entries, and tool configs, in that order, informed only by approved
    context (FR-4.2)."""
    decision_log_before = len(state.decision_log)
    failed_components_before = len(state.failed_components)

    agent = _get_ai_dev_setup_agent()
    updated = agent.run(state)

    logger.info("generate_ai_artifacts: generated %d artifact(s)", len(updated.ai_artifacts))

    return {
        "ai_artifacts": updated.ai_artifacts,
        "current_stage": PipelineStage.AI_DEVELOPMENT_SETUP,
        "decision_log": updated.decision_log[decision_log_before:],
        "failed_components": updated.failed_components[failed_components_before:],
    }


def consistency_check(state: PipelineState) -> dict:
    """Runs the Consistency Checker tool (ARCHITECTURE_v2.0.md section 5.8):
    validates generated AIArtifacts against each other and against
    org_standards. Non-blocking -- warnings are surfaced to the human at
    human_gate_2, not enforced."""
    warnings = check_consistency(state.ai_artifacts, state.org_standards)
    logger.info("consistency_check: %d inconsistency warning(s)", len(warnings))
    return {"consistency_warnings": warnings, "current_stage": PipelineStage.CONSISTENCY_CHECK}


_project_scaffolder_agent: ProjectScaffolderAgent | None = None


def _get_project_scaffolder_agent() -> ProjectScaffolderAgent:
    """Lazily construct (and cache) the real ProjectScaffolderAgent. Tests
    can set the module-level `_project_scaffolder_agent` directly to inject
    fake-LLM-backed skills."""
    global _project_scaffolder_agent
    if _project_scaffolder_agent is None:
        _project_scaffolder_agent = ProjectScaffolderAgent()
    return _project_scaffolder_agent


def generate_scaffolding(state: PipelineState) -> dict:
    """Runs the Project Scaffolding Agent (ARCHITECTURE_v2.0.md section 5.9):
    generates the folder structure, boilerplate config files, and pattern
    samples, embeds all AI artifacts (FR-5.4), and produces a README
    (FR-5.5) -- all assembled into the file manifest at
    `scaffolding_structure["files"]`."""
    decision_log_before = len(state.decision_log)
    failed_components_before = len(state.failed_components)

    agent = _get_project_scaffolder_agent()
    updated = agent.run(state)

    file_count = len((updated.scaffolding_structure or {}).get("files", {}))
    logger.info("generate_scaffolding: assembled %d file(s)", file_count)

    return {
        "scaffolding_structure": updated.scaffolding_structure,
        "current_stage": PipelineStage.PROJECT_SCAFFOLDING,
        "decision_log": updated.decision_log[decision_log_before:],
        "failed_components": updated.failed_components[failed_components_before:],
    }


# ----------------------------------------------------------------------
# Human approval gate 2 (ARCHITECTURE_v2.0.md section 5.10)
# ----------------------------------------------------------------------


def _build_gate_2_payload(state: PipelineState) -> dict:
    """FR-3.1-equivalent for gate 2 (section 5.10: "Same as 5.5"): the file
    manifest just scaffolded and any non-blocking consistency warnings."""
    manifest = (state.scaffolding_structure or {}).get("files", {})
    return {
        "stage": "human_gate_2",
        "file_count": len(manifest),
        "file_tree": sorted(manifest.keys()),
        "consistency_warnings": state.consistency_warnings,
        "ai_artifact_count": len(state.ai_artifacts),
    }


def _parse_gate_2_action(resume_value) -> HumanDecisionAction:
    if not isinstance(resume_value, dict) or "decision" not in resume_value:
        raise GateValidationError("Resume payload must be a dict with a 'decision' key.")
    try:
        action = HumanDecisionAction(resume_value["decision"])
    except ValueError:
        raise GateValidationError(
            f"Unknown decision '{resume_value.get('decision')}'. Expected 'accept' or 'revise'."
        )
    if action not in (HumanDecisionAction.ACCEPT, HumanDecisionAction.REVISE):
        raise GateValidationError(
            f"human_gate_2 only accepts 'accept' or 'revise' (reject), got '{action.value}'."
        )
    return action


def human_gate_2(state: PipelineState) -> dict:
    """Second human approval gate (ARCHITECTURE_v2.0.md section 5.10). Same
    mechanics as human_gate_1 -- dynamic `interrupt()`, validated resume,
    re-interrupt on error -- but a simpler decision set: only "accept" or
    "revise" (section 9.1's "reject", modeled as revise; see
    graph/pipeline.py's module docstring for why)."""
    decision_log_before = len(state.decision_log)
    payload = _build_gate_2_payload(state)

    while True:
        resume_value = interrupt(payload)
        try:
            action = _parse_gate_2_action(resume_value)
            justification = resume_value.get("justification")
            decision = HumanDecision(
                timestamp=_now(), action=action, finding_ids=[], justification=justification, domain=None
            )
            _record_human_decision(state, decision, gate_name="human_gate_2")
        except GateValidationError as exc:
            logger.warning("human_gate_2: rejecting resume payload: %s", exc)
            payload = {**payload, "error": str(exc)}
            continue
        break

    logger.info("human_gate_2: resolved with decision=%s", decision.action.value)
    return {
        "human_decisions": state.human_decisions,
        "current_stage": PipelineStage.HUMAN_APPROVAL_FINAL,
        "decision_log": state.decision_log[decision_log_before:],
    }


# ----------------------------------------------------------------------
# Packaging (ARCHITECTURE_v2.0.md section 3.1; BRD_v2.0.md FR-5.6)
# ----------------------------------------------------------------------


def build_zip(state: PipelineState) -> dict:
    """Runs the Zip Builder tool: writes the scaffolding file manifest to a
    downloadable `{project_name}-scaffold-{timestamp}.zip` (FR-5.6)."""
    manifest = (state.scaffolding_structure or {}).get("files", {})
    if not manifest:
        logger.warning("build_zip: empty file manifest, nothing to package for '%s'", state.project_name)
        return {"current_stage": PipelineStage.COMPLETED}

    zip_path = build_zip_tool(manifest, state.project_name, settings.scaffold_output_dir)
    logger.info("build_zip: wrote %s (%d files)", zip_path, len(manifest))
    return {"scaffold_zip_path": str(zip_path), "current_stage": PipelineStage.COMPLETED}
