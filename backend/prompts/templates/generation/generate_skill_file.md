# version: 1.0.0
# skill: generate-skill-file
# last_updated: 2026-07-08
# description: Generates a reusable AI skill file for an identified pattern

SYSTEM:
You are writing a reusable AI skill file for the "{{ pattern_name }}"
pattern -- a task definition an AI coding assistant will invoke whenever it
needs to implement this pattern in this project (FR-4.7.1).

COMPONENTS:
{{ components_context }}

CODING STANDARD:
{{ coding_standard }}

TESTING STANDARD:
{{ testing_standard }}

API DESIGN STANDARD:
{{ api_design_standard }}

INSTRUCTIONS.MD CONVENTIONS (this skill file must inherit these -- FR-4.7.3):
{{ instructions_md_conventions }}

TASK:
Write the skill file for "{{ pattern_name }}". It should define: what the
pattern is for, when to apply it, the concrete steps to implement it using
this project's actual tech stack and components, and how it complies with
the coding/testing/API conventions above. Make it specific enough that an AI
assistant could follow it verbatim -- reference real component names where
relevant, not generic placeholders.

OUTPUT:
Return structured output matching the provided schema: the skill file's
content as a single string.
