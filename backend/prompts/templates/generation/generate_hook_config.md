# version: 1.0.0
# skill: generate-hook-config
# last_updated: 2026-07-08
# description: Generates a hook configuration for a given hook type

SYSTEM:
You are writing the "{{ hook_type }}" hook configuration for this project
(FR-4.8.1: pre-commit validation, PR templates, lint rules, formatting
rules, architecture validation, security checks, or dependency validation).

CI/CD STANDARD:
{{ cicd_standard }}

CODING STANDARD:
{{ coding_standard }}

REPOSITORY CONVENTIONS STANDARD:
{{ repository_conventions_standard }}

INSTRUCTIONS.MD CONVENTIONS (this hook must enforce these -- FR-4.8.3):
{{ instructions_md_conventions }}

TASK:
Write the "{{ hook_type }}" hook configuration. It must enforce what
instructions.md and the org standards above already define -- do not invent
new rules that aren't grounded in one of those sources. Use whatever format
is conventional for this hook type (e.g. a pre-commit config, a PR template,
a lint ruleset) and be concrete: real rule names/patterns, not placeholders.

OUTPUT:
Return structured output matching the provided schema: the hook
configuration's content as a single string.
