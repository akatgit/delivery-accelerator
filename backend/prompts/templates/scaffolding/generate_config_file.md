# version: 1.0.0
# skill: generate-config-file
# last_updated: 2026-07-08
# description: Generates a boilerplate configuration file for the given config type

SYSTEM:
You are writing the "{{ config_type }}" configuration file for this project
(FR-5.2: Docker, environment configs, CI/CD pipeline definitions).

TECH STACK:
{{ tech_stack_context }}

CI/CD STANDARD:
{{ cicd_standard }}

TASK:
Write the "{{ config_type }}" file, specific to this project's actual tech
stack (real base images, package managers, build/run commands -- not
placeholders). Where the CI/CD standard above speaks to this config type,
follow it precisely; otherwise use general best practices for this tech
stack.

OUTPUT:
Return structured output matching the provided schema: the config file's
content as a single string.
