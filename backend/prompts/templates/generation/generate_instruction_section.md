# version: 1.0.0
# skill: generate-instruction-section
# last_updated: 2026-07-08
# description: Generates one section of instructions.md for a given category

SYSTEM:
You are writing the "{{ category }}" section of instructions.md, the
project-wide engineering standards document every AI coding assistant and
human contributor will read (FR-4.6.1).

TECH STACK:
{{ tech_stack_context }}

COMPONENTS:
{{ components_context }}

ACCEPTED FINDINGS (reflect each as an explicit rule in this section, where relevant):
{{ accepted_findings_context }}

{% if org_standard_content %}
ORGANIZATION STANDARD FOR THIS CATEGORY:
{{ org_standard_content }}
CRITICAL: Follow this standard precisely. Do not contradict it, and do not
substitute general best practices where this standard already speaks.
{% else %}
No organization standard was provided for "{{ category }}". Generate this
section from general engineering best practices for this project's tech
stack, and begin the section with a clearly visible warning, e.g.:
"> **Default guidance** -- no organization standard was provided for this
category; the following reflects general best practices, not an approved
organizational policy."
{% endif %}

TASK:
Write the "{{ category }}" section of instructions.md as markdown, starting
with a level-2 heading (`## {{ category }}`). Be specific to this project's
actual components and tech stack -- avoid generic statements that could
apply to any project. Where an accepted finding recommends something
specific, state it as an explicit rule, not a vague suggestion.

OUTPUT:
Return structured output matching the provided schema: the section's
markdown content as a single string.
