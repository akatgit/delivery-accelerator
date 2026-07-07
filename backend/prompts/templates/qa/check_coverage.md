# version: 1.0.0
# skill: check-coverage
# last_updated: 2026-07-08
# description: Flags reviewers with suspiciously low finding counts for a complex architecture

SYSTEM:
You are checking whether each reviewer's finding count makes sense given how
complex this architecture actually is.

COMPONENT COUNT: {{ component_count }}

COMPONENTS:
{{ components_summary }}

REVIEW SUMMARIES (per domain, score and finding count):
{{ review_summaries }}

TASK:
Complexity indicators that make zero (or very few) findings suspicious
include: more than 5 components, a microservices or distributed-systems style
(multiple independent services, message queues, multiple databases), or a
high component count relative to typical projects.

For each domain whose finding count looks suspiciously low given the
architecture's complexity, report:
- domain: the domain name
- warning: why zero (or very few) findings is suspicious here, and which
  complexity indicator makes it so

Do not flag a domain just because its finding count is lower than another
domain's -- only flag it if the architecture's complexity makes it
implausible that so few issues exist in that domain.

If every domain's finding count looks plausible, return an empty array.

OUTPUT:
Return structured output matching the provided schema.
