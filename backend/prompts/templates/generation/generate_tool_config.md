# version: 1.0.0
# skill: generate-tool-config
# last_updated: 2026-07-08
# description: Fills a tool-specific config template with project-specific guidance from instructions.md

SYSTEM:
You are generating the AI assistant configuration file for "{{ tool_name }}",
using its structural template below.

TOOL TEMPLATE (fill in every bracketed placeholder, e.g. [ARCHITECTURE
GUIDANCE], with real content; keep the surrounding structure, headers, and
formatting conventions intact):
{{ tool_template }}

INSTRUCTIONS.MD (the project's full engineering standards -- the source of
truth for every section below):
{{ instructions_md_content }}

PROJECT CONTEXT SUMMARY:
{{ project_context_summary }}

TASK:
Fill in the tool template above so it conveys guidance EQUIVALENT to what
instructions.md establishes, adapted to "{{ tool_name }}"'s own conventions
and level of detail (FR-4.10.3: different tool configs must produce
equivalent guidance, not necessarily identical wording or structure). Do not
introduce guidance that contradicts instructions.md. Do not leave any
bracketed placeholder unfilled, and do not alter the template's existing
structure, headers, or formatting conventions beyond filling in placeholders.

OUTPUT:
Return structured output matching the provided schema: the complete,
filled-in tool configuration file content as a single string.
