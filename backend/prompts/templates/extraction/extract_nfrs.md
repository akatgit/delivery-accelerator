# version: 1.0.0
# skill: extract-nfrs
# last_updated: 2026-07-07
# description: Extracts non-functional requirements from the BRD, with components context

SYSTEM:
You are extracting non-functional requirements (NFRs) for a software project
from its business requirements document (BRD).

COMPONENTS (already extracted):
{{ components_context }}

BRD DOCUMENT:
{{ brd_content }}

TASK:
Identify every non-functional requirement stated or clearly implied in the BRD
-- performance, scalability, security, reliability, compliance, usability,
maintainability, and similar cross-cutting concerns. For each NFR, report:
- category: the concern it belongs to (e.g. "performance", "security",
  "availability", "compliance")
- requirement: the requirement itself, stated specifically and measurably
  where the source supports it
- source: the section or sentence of the BRD it comes from
- measurable: true if the requirement includes a concrete, testable target
  (e.g. "p99 latency under 200ms"), false if it is qualitative
- notes: any clarifying detail, otherwise null

Where a requirement clearly applies to one of the components listed above,
prefer wording that references that component by its exact name.

OUTPUT:
Return the extracted NFRs as structured output matching the provided schema.
