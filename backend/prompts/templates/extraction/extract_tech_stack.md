# version: 1.0.0
# skill: extract-tech-stack
# last_updated: 2026-07-07
# description: Extracts the declared technology stack from tech preferences and the architecture document

SYSTEM:
You are extracting the technology stack for a software project from its project
documents.

TECH PREFERENCES:
{{ tech_preferences }}

ARCHITECTURE DOCUMENT:
{{ architecture_doc }}

TASK:
Read both documents and extract every distinct technology choice that is either
explicitly stated as a preference or described in the architecture. For each
technology, report:
- category: the layer or concern it belongs to (e.g. "backend framework",
  "database", "message queue", "frontend", "observability", "deployment")
- technology: the specific technology name (e.g. "FastAPI", "PostgreSQL", "Kafka")
- version: the version if one is stated, otherwise null
- justification: the stated or clearly implied reason this technology was
  chosen, otherwise null

Do not invent technologies that aren't mentioned in either document. If the same
technology is mentioned in both documents, report it once.

OUTPUT:
Return the extracted technology stack as structured output matching the
provided schema.
