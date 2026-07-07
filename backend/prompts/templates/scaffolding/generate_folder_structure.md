# version: 1.0.0
# skill: generate-folder-structure
# last_updated: 2026-07-08
# description: Generates the project folder structure aligned with component design

SYSTEM:
You are designing the project's folder structure, aligned with its
architecture (FR-5.1).

TECH STACK:
{{ tech_stack_context }}

COMPONENTS:
{{ components_context }}

EXISTING CODEBASE:
{{ existing_codebase_context }}

TASK:
Produce a directory tree for this project. Each component above should have
a clear, corresponding location in the tree. If an existing codebase was
provided, the new structure must integrate with it (reuse its top-level
layout, don't propose a conflicting one) rather than replacing it wholesale.
If no existing codebase was provided, design a clean, idiomatic layout for
this tech stack.

Represent the tree as a nested object: each key is a file or folder name;
a folder's value is a nested object of its own contents; a file's value is
the string "file". For example:
{"backend": {"agents": {}, "main.py": "file"}, "README.md": "file"}

OUTPUT:
Return structured output matching the provided schema: the directory tree
as a nested JSON object under `tree`.
