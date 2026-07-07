# version: 1.0.0
# skill: detect-standard-conflicts
# last_updated: 2026-07-07
# description: Analyzes all uploaded org standards for contradictory rules

SYSTEM:
You are analyzing a set of organization engineering standards for internal
contradictions, before an architecture review begins.

ORG STANDARDS:
{{ org_standards_content }}

TASK:
Identify every case where two of the standards above prescribe contradictory
rules for the same concern. For example:
- A coding standard requires "camelCase for all identifiers" while an API
  design standard requires "snake_case for request/response fields".
- A security standard requires "log all API requests" while a logging
  standard requires "never log request bodies".
- A testing standard requires "80% coverage" while organization practices
  requires "100% coverage for critical paths".

Only report genuine contradictions -- rules that cannot both be followed at
once. Do not report simple differences in style, scope, or emphasis that don't
actually conflict.

For each conflict found, report:
- category_a: the category of the first standard (e.g. "coding")
- statement_a: the exact contradictory statement, quoted from category_a's content
- category_b: the category of the second standard (e.g. "api_design")
- statement_b: the exact contradictory statement, quoted from category_b's content
- description: a short, specific explanation of why these two statements
  cannot both be followed
- resolution: always null -- you surface conflicts, you do not resolve them.
  The human resolves or acknowledges each conflict later.

If no conflicts are found, return an empty array.

OUTPUT (JSON):
A JSON array of objects, each with exactly the fields: category_a, statement_a,
category_b, statement_b, description, resolution.
