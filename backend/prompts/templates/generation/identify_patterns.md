# version: 1.0.0
# skill: identify-patterns
# last_updated: 2026-07-08
# description: Determines which architectural/implementation patterns this project needs

SYSTEM:
You are identifying the architectural and implementation patterns this
project needs, so sample implementations can be generated for each one later.

TECH STACK:
{{ tech_stack_context }}

COMPONENTS:
{{ components_context }}

NON-FUNCTIONAL REQUIREMENTS:
{{ nfrs_context }}

ACCEPTED FINDINGS (only findings the human has approved inform this):
{{ accepted_findings_context }}

TASK:
Identify the distinct patterns this project should adopt -- e.g. repository
pattern for data access, circuit breaker for external calls, event-driven
pub/sub for async workflows, retry-with-backoff, API gateway pattern, CQRS,
saga pattern for distributed transactions. Base each pattern on the project's
actual components and tech stack, its NFRs (e.g. a reliability NFR implies
resilience patterns), and any accepted findings that recommend a specific
pattern.

Do not invent patterns with no basis in the project context above. Do not
list generic language features (e.g. "use classes") -- only genuine
architectural or implementation patterns.

For each pattern, report:
- name: a short, conventional name for the pattern
- description: what it does and why this project needs it
- applicable_components: which of the components above it applies to (use
  exact component names)

If no patterns are clearly warranted, return an empty array.

OUTPUT:
Return structured output matching the provided schema.
