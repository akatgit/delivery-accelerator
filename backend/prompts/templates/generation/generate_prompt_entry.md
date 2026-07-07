# version: 1.0.0
# skill: generate-prompt-entry
# last_updated: 2026-07-08
# description: Generates a project-specific prompt library entry for a given category

SYSTEM:
You are writing a project-specific prompt library entry for the
"{{ category }}" category (FR-4.9.1: service generation, API implementation,
database access, event publishing, testing, refactoring, or code review).
Developers and AI assistants will use this prompt verbatim to kick off that
kind of task in this project.

TECH STACK:
{{ tech_stack_context }}

INSTRUCTIONS.MD CONVENTIONS (this prompt must be tuned to these -- FR-4.9.2):
{{ instructions_md_conventions }}

TASK:
Write a ready-to-use prompt for "{{ category }}" tasks in this project. It
must be specific to the actual tech stack above (name real frameworks,
libraries, and patterns in use) and must reflect the conventions from
instructions.md (naming, structure, error handling, testing expectations,
etc.), not generic advice that could apply to any project.

OUTPUT:
Return structured output matching the provided schema: the prompt entry's
content as a single string.
