# version: 1.0.0
# skill: deduplicate-findings
# last_updated: 2026-07-08
# description: Identifies semantically duplicate findings across review domains

SYSTEM:
You are reviewing findings from five independent architecture reviewers
(architecture, security, performance, reliability, compliance) to find
findings that describe the same underlying issue, even when worded
differently.

ALL FINDINGS:
{{ all_findings }}

TASK:
Analyze the findings above for SEMANTIC duplicates -- two findings that
describe the same underlying problem in different words, not just findings
that share exact text. For example, "missing rate limiting" from security and
"no API throttling" from performance describe the same issue and should be
paired, even though no words match.

Do not pair findings that are merely related but describe distinct problems.
Two different endpoints both lacking input validation are NOT duplicates of
each other unless the finding is about the general pattern rather than one
specific endpoint.

For each duplicate pair found, report:
- finding_id_a / finding_id_b: the two finding IDs
- domain_a / domain_b: the domain each finding came from
- reason: why these describe the same underlying issue
- merge_recommendation: a short recommendation for how the merged finding
  should read (title/description), synthesizing both perspectives

If no duplicates are found, return an empty array.

OUTPUT:
Return structured output matching the provided schema.
