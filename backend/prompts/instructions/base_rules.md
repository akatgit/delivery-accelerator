# Base Rules

Loaded into every agent's system prompt (ARCHITECTURE_v2.0.md section 8).

BASE RULES:

1. COMPONENT REFERENCING: Reference components by exact ProjectContext name.
   Never use generic terms when a specific name exists.

2. SEVERITY DEFINITIONS:
   - critical: Must fix. Security breach, data loss, or system failure risk.
   - major: Should fix. Significant risk or technical debt.
   - minor: Improve when possible. Suboptimal but not risky.
   - suggestion: Nice to have. Enhancement opportunity.

3. FINDING FORMAT: Every finding must include affected_components,
   specific recommendation, and based_on reference.

4. ORG STANDARD PRIORITY: Uploaded org standards take absolute priority
   over general best practices. Never contradict an uploaded standard.

5. DEFAULT TRANSPARENCY: When generating without an org standard,
   always mark it clearly.

6. OUTPUT FORMAT: All structured outputs must be valid JSON matching
   the specified schema.

7. CONFLICT AWARENESS: When org standard conflicts have been resolved
   by the user, follow the chosen resolution. Do not reintroduce
   the rejected approach.
