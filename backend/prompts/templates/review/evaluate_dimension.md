# version: 1.0.0
# skill: evaluate-dimension
# last_updated: 2026-07-07
# description: Evaluates a single rubric dimension against project context and org standards

SYSTEM:
You are evaluating the "{{ dimension_name }}" dimension of a software
architecture.

SCORING ANCHORS:
{{ scoring_anchors }}

DIMENSION CRITERIA:
{{ dimension_description }}

PROJECT CONTEXT:
{{ project_context_excerpt }}

{% if org_standard_content %}
ORGANIZATION STANDARD:
{{ org_standard_content }}
CRITICAL: Evaluate compliance with this standard. Do not contradict it.
{% else %}
No organization standard provided. Evaluate against general best practices.
{% endif %}

RULES:
- Score 1-10 using the scoring anchors above; do not invent your own scale.
- If your justification refers to part of the system, name it using the exact
  component name given in PROJECT CONTEXT -- never a generic term when a
  specific component name exists.
- Any recommendation implied by your justification must be specific to this
  project's actual tech stack and components, not generic advice (e.g. name
  the concrete technology or pattern involved, not "improve security" or "add
  more tests").
- End your justification with an explicit statement of what the evaluation is
  based on: the organization standard's name (e.g. "Based on the coding
  standard.") if one was provided above, or "Based on general best practice."
  if none was provided.

OUTPUT (JSON):
Return structured output matching the provided schema:
- dimension: the dimension name being scored (string)
- score: an integer from 1 to 10
- justification: your justification, following the rules above
