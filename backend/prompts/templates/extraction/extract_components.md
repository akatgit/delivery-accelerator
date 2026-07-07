# version: 1.0.0
# skill: extract-components
# last_updated: 2026-07-07
# description: Extracts architectural components from the architecture document, with tech stack context

SYSTEM:
You are extracting the architectural components of a software project from its
architecture document.

TECH STACK (already extracted):
{{ tech_stack_context }}

ARCHITECTURE DOCUMENT:
{{ architecture_doc }}

TASK:
Identify every distinct architectural component described in the document
(e.g. services, modules, gateways, workers, databases treated as owned
components). For each component, report:
- name: the component's exact name as used in the document
- type: its kind (e.g. "service", "gateway", "worker", "database", "frontend")
- description: what it does, in 1-3 sentences
- tech_stack: the subset of the tech stack above that this component uses
- responsibilities: a list of its distinct responsibilities
- dependencies: names of other components it depends on
- api_contracts: any API endpoints or contracts it exposes, if described
- data_entities: any data entities it owns or manages, if described

Use the exact component names from the document consistently -- other parts of
the pipeline reference components by these names.

OUTPUT:
Return the extracted components as structured output matching the provided
schema.
