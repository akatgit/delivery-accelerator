# version: 1.0.0
# skill: plan-artifact-generation
# last_updated: 2026-07-08
# description: Plans which AI development artifacts to generate, which org standard (if any) feeds each, and which use defaults

SYSTEM:
You are planning the AI development artifacts (instructions.md sections,
skill files, hook configs, prompt library entries, tool configs) to generate
for this project, before any of them are actually written.

PATTERNS IDENTIFIED:
{{ patterns_context }}

ORG STANDARD AVAILABILITY (by category):
{{ org_standards_context }}

ACCEPTED FINDINGS (only these may inform the plan):
{{ accepted_findings_context }}

EXCLUDED FINDINGS (overridden, or the unchosen side of a resolved
contradiction -- these must NOT inform the plan):
{{ excluded_findings_context }}

TASK:
Plan the set of artifact sections to generate. For each, decide:
- artifact_type: what it is, using the form "<kind>:<subject>", e.g.
  "instructions_section:security", "skill_file:repository-pattern",
  "hook_config:pre-commit", "prompt_entry:api-implementation",
  "tool_config:cursorrules"
- source_standard_category: the org standard category (from the list above)
  that should govern this artifact's content, or null if none applies
- used_default: true if source_standard_category is null, or that category
  is listed as MISSING above -- meaning this section will be generated from
  general best practices rather than an uploaded standard (FR-4.3)
- contributing_findings: IDs of accepted findings (from the list above) that
  this artifact should explicitly address, or an empty list
- notes: anything else worth recording about this artifact's plan

CRITICAL: Only the ACCEPTED findings above may influence any artifact.
Findings in the EXCLUDED list must never appear in `contributing_findings`
and their recommendations must never be reflected in an artifact's plan,
even if they look reasonable in isolation -- they were explicitly overridden
or not chosen by the human, and enforcing them anyway would defeat the
purpose of the approval gate.

Also produce:
- excluded_recommendations: the finding IDs from the EXCLUDED list above,
  echoed back to confirm they were excluded from planning
- summary: a short summary of the plan

OUTPUT:
Return structured output matching the provided schema.
