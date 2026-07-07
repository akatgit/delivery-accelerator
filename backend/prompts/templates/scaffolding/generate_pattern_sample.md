# version: 1.0.0
# skill: generate-pattern-sample
# last_updated: 2026-07-08
# description: Generates a sample implementation, test file, and usage header for an identified pattern

SYSTEM:
You are writing the sample implementation for the "{{ pattern_name }}"
pattern (FR-5.3): a working reference implementation, its test file, and a
usage header explaining how to use it.

PATTERN DESCRIPTION:
{{ pattern_description }}

APPLICABLE COMPONENTS:
{{ applicable_components }}

CODING STANDARD:
{{ coding_standard }}

TESTING STANDARD:
{{ testing_standard }}

INSTRUCTIONS.MD CONVENTIONS:
{{ instructions_md_conventions }}

TASK:
Produce three things for "{{ pattern_name }}":
- implementation: a complete, working sample implementation of the pattern,
  using this project's actual tech stack and conventions above
- test_file: a test file exercising the sample implementation, following the
  testing standard above where provided
- usage_header: a short header comment/docstring explaining what the
  pattern does, when to use it, and how to import/invoke the sample

OUTPUT:
Return structured output matching the provided schema, with all three
fields filled in.
