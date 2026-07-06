# Implementation Guide v2.0 — Agentic Solution Delivery Accelerator

**Version:** 2.0
**Last updated:** 2026-07-06

## How to use this guide

Each step produces a specific deliverable. Feed the prompt to your AI coding tool along with the referenced docs. Complete each step before moving to the next.

**Context files to keep open throughout:**
- `docs/BRD_v2.0.md`
- `docs/ARCHITECTURE_v2.0.md`

---

## Step 1 — Project bootstrap

**Produces:** Folder structure, dependencies, config, entry point

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 14 (Project structure) and section 2 (Tech stack).

Create the complete folder structure as defined. Generate:
1. pyproject.toml with: langchain, langgraph, langchain-anthropic, langsmith, fastapi, uvicorn, pydantic, python-dotenv, jinja2, pyyaml, python-multipart
2. backend/config.py — env config (ANTHROPIC_API_KEY, LANGSMITH_API_KEY, LANGSMITH_PROJECT, DATABASE_URL, MAX_RETRIES=2, CHUNK_SIZE=6000, CHUNK_OVERLAP=500)
3. backend/main.py — FastAPI app with CORS, health endpoint
4. .env.example
5. Empty __init__.py in all packages

Skeleton only — no business logic.
```

---

## Step 2 — Core schemas

**Produces:** All Pydantic models

**Prompt:**
```
Read docs/BRD_v2.0.md section 12 (ProjectContext schema) — all subsections including StandardConflict, ReviewQAResult, Contradiction, FailedComponent.

Create with full Pydantic v2 models:

1. backend/schemas/project_context.py
   - TechStackItem, Component, NFR, Story, Gap, ExistingCodebase
   - StandardConflict (category_a, statement_a, category_b, statement_b, description, resolution)
   - OrgStandards (all category fields + missing_categories + conflicts list)
   - ProjectContext (root model, all fields from 12.1 through 12.4)

2. backend/schemas/review.py
   - ReviewDomain enum, Severity enum, FindingStatus enum
   - DimensionScore, Finding (include duplicate_of, contributing_domains fields)
   - ReviewResult, RubricDimension, ReviewRubric

3. backend/schemas/review_qa.py
   - Contradiction, ReviewQAResult (quality_score, duplicates_found, contradictions, severity_normalizations, low_quality_findings, coverage_warnings, summary)

4. backend/schemas/artifacts.py
   - PatternDefinition, AIArtifact (with used_default and prompt_version fields)

5. backend/schemas/pipeline.py
   - HumanDecision (include "resolve_contradiction" action type)
   - DecisionEntry (include skill and prompt_version fields)
   - FailedComponent
   - Pipeline stage enum

All Pydantic v2 syntax. Docstrings on every model.
```

---

## Step 3 — Base classes with production features

**Produces:** Foundation with chunking, retry, validation, prompt versioning

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md sections 3.3 (Layered design), 4.1 (Chunking strategy), 4.2 (Error handling), 4.3 (Prompt versioning), and 8 (Instructions — base rules).

Create:

1. backend/prompts/instructions/base_rules.md
   - Base rules from ARCHITECTURE section 8 verbatim

2. backend/skills/base.py — BaseSkill class:
   - name, description, prompt_template_path, output_schema (Pydantic model)
   - max_input_tokens: int (threshold for chunking, default 6000)
   - chunk_merge_strategy: str ("union" or "merge_and_deduplicate")

   Core method — invoke(inputs: dict) -> dict:
   a. Load prompt template from file, extract version from header
   b. Fill template parameters from inputs
   c. Check if input exceeds max_input_tokens:
      - If yes: split using RecursiveCharacterTextSplitter, run LLM on each chunk, merge results using chunk_merge_strategy
      - If no: run LLM directly
   d. Validate output against output_schema (Pydantic)
   e. If validation fails: retry with error-correction prompt (up to MAX_RETRIES)
   f. If LLM call fails (timeout, rate limit): retry with exponential backoff (up to MAX_RETRIES)
   g. Log to decision log: skill name, prompt version, inputs summary, output summary
   h. LangSmith tracing on every invocation with prompt_version in metadata

   Graceful degradation:
   - After all retries exhausted, raise SkillFailedError with details
   - The calling agent catches this and logs to failed_components

3. backend/agents/base.py — BaseAgent class:
   - name, skills list, base_instructions (loaded from base_rules.md)
   - run(state) -> state: subclasses implement
   - Wraps skill invocations with try/except SkillFailedError
   - Logs failed skills to state.failed_components
   - LangSmith tracing

4. backend/agents/reviewers/base_reviewer.py — BaseReviewer(BaseAgent):
   - rubric: ReviewRubric (loaded from YAML)
   - org_standard_categories: list[str]
   - run() implementation:
     a. Extract relevant org standards from state.org_standards using org_standard_categories
     b. For each rubric dimension: invoke evaluate-dimension skill with dimension criteria + org standard + project context
     c. If a dimension skill fails: log it, continue with remaining dimensions, note the gap
     d. Aggregate completed dimension results into ReviewResult
     e. Domain score = average of completed dimension scores

Include comprehensive error handling and logging throughout.
```

---

## Step 4 — Rubric YAMLs

**Produces:** Review rubrics as data

**Prompt:**
```
Read docs/BRD_v2.0.md section 13 (Review rubrics) — all subsections.

Create:
1. backend/rubrics/architecture.yaml — org_standard_categories: [coding, api_design, naming, repository_conventions]
2. backend/rubrics/security.yaml — org_standard_categories: [security, api_design]
3. backend/rubrics/performance.yaml — org_standard_categories: [api_design, logging]
4. backend/rubrics/reliability.yaml — org_standard_categories: [logging, exception_handling, testing]
5. backend/rubrics/compliance.yaml — org_standard_categories: [cicd, organization_practices]

Each with: domain, org_standard_categories, weight, dimensions (name, description, scoring_guide with 1-2/3-4/5-6/7-8/9-10 anchors).

6. backend/rubrics/loader.py — loads YAML into ReviewRubric model.
```

---

## Step 5 — LangGraph pipeline skeleton

**Produces:** Complete graph with placeholder nodes, including QA agent node

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 9 (LangGraph state machine).

Create:

1. backend/graph/state.py — LangGraph state type based on ProjectContext

2. backend/graph/nodes.py — placeholder functions for ALL nodes:
   - parse_documents, detect_standard_conflicts
   - architecture_reviewer, security_reviewer, performance_reviewer, reliability_reviewer, compliance_reviewer
   - aggregate_reviews, review_qa (NEW), human_gate_1
   - synthesize_context, generate_ai_artifacts, consistency_check
   - generate_scaffolding, human_gate_2, build_zip

3. backend/graph/pipeline.py — full StateGraph:
   - All nodes added
   - route_to_reviewers with Send() for 5 parallel nodes
   - aggregate_reviews → review_qa → human_gate_1 (this sequence is critical)
   - human_gate_1 conditional: revise → parse_documents, accept → synthesize_context
   - SqliteSaver checkpointer
   - interrupt_before on both human gates

Graph must compile and run end-to-end with placeholders.
```

**Verify:** Run with dummy data. LangSmith should show: parse → 5 parallel reviewers → aggregate → QA → human gate.

---

## Step 6 — Standards loader + conflict detection

**Produces:** Load standards deterministically + detect conflicts via LLM

**Prompt:**
```
Read docs/BRD_v2.0.md section 14 (Org standards management) and docs/ARCHITECTURE_v2.0.md section 4.4 (Conflict detection).

Create:

1. backend/tools/standards_loader.py (no LLM):
   - load_standards(dir) -> OrgStandards: reads files, maps filenames to categories, populates missing_categories
   - route_standards(org_standards, target_categories) -> str: concatenates relevant standards

2. backend/skills/extraction/detect_standard_conflicts.py (LLM skill):
   - Input: all org standard contents concatenated with category headers
   - Output: list[StandardConflict]
   - Prompt: analyze all standards for contradictory rules, report each conflict with both source categories and statements
   - Create prompt template at backend/prompts/templates/extraction/detect_standard_conflicts.md with version header

Include unit tests for both.
```

---

## Step 7 — Extraction skills

**Produces:** Five extraction skills with chunking support

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 6.1 (Extraction skills) and section 5.1 (Document parsing agent).

Create 5 skills extending BaseSkill, each with chunking enabled for large docs:

1. backend/skills/extraction/extract_tech_stack.py
   - max_input_tokens: 6000, chunk_merge_strategy: "merge_and_deduplicate"
   - Input: tech prefs + arch doc content. Output: list[TechStackItem]

2. backend/skills/extraction/extract_components.py
   - max_input_tokens: 6000, chunk_merge_strategy: "merge_and_deduplicate"
   - Input: arch doc + tech_stack context. Output: list[Component]

3. backend/skills/extraction/extract_nfrs.py
   - Input: BRD + components context. Output: list[NFR]

4. backend/skills/extraction/extract_stories.py
   - Input: stories doc + components context. Output: list[Story]

5. backend/skills/extraction/identify_gaps.py
   - Input: full ProjectContext. Output: list[Gap]

Create prompt templates in backend/prompts/templates/extraction/ for each.
Each template must have a version header (# version: 1.0.0).
Each skill uses with_structured_output() for reliable parsing.
```

---

## Step 8 — Document parsing agent

**Produces:** First real agent wiring skills together

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 5.1 (Document parsing agent).

Create backend/agents/document_parser.py — DocumentParsingAgent(BaseAgent):

1. Load and categorize org standards (standards_loader tool — no LLM)
2. Detect conflicts between standards (detect_standard_conflicts skill — LLM)
3. Extract in sequence, passing accumulated context:
   a. extract_tech_stack
   b. extract_components
   c. extract_nfrs
   d. extract_stories
   e. identify_gaps
4. If any extraction skill fails: log to failed_components, continue with remaining

Update graph/nodes.py to wire this agent.
```

**Verify:** Upload sample docs. Confirm ProjectContext populated. Check LangSmith shows sequential skill calls. Test with a large doc to verify chunking.

---

## Step 9 — Evaluate-dimension skill

**Produces:** The core review skill used by all 5 reviewers

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md sections 6.2 (Review skills) and 7.1 (Template structure).

Create backend/skills/review/evaluate_dimension.py — EvaluateDimensionSkill(BaseSkill):

Input: dimension_name, dimension_description, scoring_anchors, project_context_excerpt, org_standard_content (or null)
Output: DimensionScore

Create prompt template at backend/prompts/templates/review/evaluate_dimension.md:
- Version header
- System: "You are evaluating the {dimension_name} dimension..."
- Scoring anchors
- Dimension criteria
- Project context (relevant sections only)
- Conditional org standard block (if provided: evaluate compliance; if not: general best practices)
- Output JSON schema
- Rules: affected_components must match real component names, recommendations must be tech-stack-specific, based_on must cite org standard name or "general best practice"
```

---

## Step 10 — Five reviewer agents

**Produces:** All reviewers using shared base + evaluate-dimension

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 5.2 (Review board) routing table.

Create 5 minimal reviewer files — each only defines configuration:

1. backend/agents/reviewers/architecture.py — categories: [coding, api_design, naming, repository_conventions]
2. backend/agents/reviewers/security.py — categories: [security, api_design]
3. backend/agents/reviewers/performance.py — categories: [api_design, logging]
4. backend/agents/reviewers/reliability.py — categories: [logging, exception_handling, testing]
5. backend/agents/reviewers/compliance.py — categories: [cicd, organization_practices]

All inherit BaseReviewer. Execution logic is in the base class.
Update graph/nodes.py with real reviewers.
Update route_to_reviewers to instantiate and invoke each.
```

**Verify:** Full pipeline with sample docs + org standards. 5 parallel reviewers in LangSmith. Each produces scored ReviewResult.

---

## Step 11 — Review aggregator

**Produces:** Deterministic merge + scoring

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 5.3 (Review aggregator).

Create backend/tools/aggregator.py:
- aggregate_reviews(reviews: list[ReviewResult], failed_domains: list[str]) -> dict:
  - Merge all findings, sort by severity
  - Compute weighted overall score (exclude failed domains, redistribute weights)
  - Generate remediation summary
  - threshold_passed: overall_score >= 6.0

No LLM. Update graph/nodes.py.
```

---

## Step 12 — Review QA agent

**Produces:** Quality validation of review output before human sees it

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 5.4 (Review QA agent) and docs/BRD_v2.0.md FR-2.10.

Create:

1. backend/skills/qa/deduplicate_findings.py
   - Input: all findings across all domains
   - LLM performs semantic similarity analysis (not string matching)
   - Output: list of duplicate pairs with merge recommendation
   - Template: backend/prompts/templates/qa/deduplicate_findings.md

2. backend/skills/qa/detect_contradictions.py
   - Input: all findings and their recommendations
   - LLM identifies opposing recommendations between reviewers
   - Output: list[Contradiction] with both positions and context
   - Template: backend/prompts/templates/qa/detect_contradictions.md

3. backend/skills/qa/validate_actionability.py
   - Input: all findings + list of valid component names from ProjectContext
   - LLM checks: real component refs? tech-stack-specific recommendations?
   - Output: list of low-quality finding IDs with reasons
   - Template: backend/prompts/templates/qa/validate_actionability.md

4. backend/skills/qa/check_coverage.py
   - Input: ReviewResults + component count + architecture style
   - LLM evaluates: suspicious zero-finding reviewers for complex architectures?
   - Output: coverage warnings
   - Template: backend/prompts/templates/qa/check_coverage.md

5. backend/agents/review_qa.py — ReviewQAAgent(BaseAgent):
   - Invokes all 4 QA skills
   - Applies deduplication: merge findings, preserve higher severity, add contributing_domains
   - Applies severity normalization
   - Computes quality score (1-10)
   - Writes ReviewQAResult to state

Update graph/nodes.py. QA runs AFTER aggregator, BEFORE human gate.
```

**Verify:** Run pipeline. Check that duplicate findings are merged, contradictions flagged. Review quality score appears in state.

---

## Step 13 — Human approval gate

**Produces:** Interrupt + resume with override/contradiction resolution logic

**Prompt:**
```
Read docs/BRD_v2.0.md FR-3 (Human approval gate) including contradiction resolution.

Update backend/graph/nodes.py — human_gate_1:
- Uses LangGraph interrupt()
- On resume, processes decision:
  - "accept": mark all findings as accepted
  - "override": validate justifications (min 20 chars), critical finding confirmation, mark overridden, log decisions
  - "revise": increment review_iteration (max 5), route back to parse_documents
  - "resolve_contradiction": for each contradiction, record which recommendation chosen, mark unchosen as resolved
- All decisions logged to decision_log with timestamps

Update graph/pipeline.py:
- human_gate_1 conditional edge:
  - revise → parse_documents
  - accept/override → synthesize_context
```

---

## Step 14 — Context synthesis agent

**Produces:** Bridge between review and generation

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 5.6 (Context synthesis agent).

Create:
1. backend/skills/generation/identify_patterns.py — determines patterns needed
2. backend/skills/generation/plan_artifact_generation.py — creates generation plan including which standards feed which artifacts, which sections use defaults
3. backend/agents/context_synthesizer.py — invokes both skills, writes to state

Plan must respect contradiction resolutions: chosen approach included, unchosen excluded.
Create prompt templates with version headers.
Update graph/nodes.py.
```

---

## Step 15 — Generation skills

**Produces:** All skills for AI artifact generation

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 6.4 (Generation skills) and section 5.7 (AI dev setup agent).

Create 5 generation skills:

1. backend/skills/generation/generate_instruction_section.py
   - Input: category, org_standard_content (or null), accepted_findings, tech_stack, components
   - Org standard present: follow precisely. Missing: LLM best practices + default warning.
   - Template: backend/prompts/templates/generation/generate_instruction_section.md

2. backend/skills/generation/generate_skill_file.py
   - Input: pattern_name, components, org standards (coding, testing, API), instructions.md conventions
   - Template: backend/prompts/templates/generation/generate_skill_file.md

3. backend/skills/generation/generate_hook_config.py
   - Input: hook_type, org standards (CI/CD, coding, repo), instructions.md conventions
   - Template: backend/prompts/templates/generation/generate_hook_config.md

4. backend/skills/generation/generate_prompt_entry.py
   - Input: category, tech_stack, instructions.md conventions
   - Template: backend/prompts/templates/generation/generate_prompt_entry.md

5. backend/skills/generation/generate_tool_config.py
   - Input: tool_name, tool_template, instructions.md content, project context summary
   - Template: backend/prompts/templates/generation/generate_tool_config.md

Create tool templates: backend/templates/tools/cursorrules.j2, copilot-instructions.j2, slingshot-config.j2
All prompt templates versioned.
```

---

## Step 16 — AI development setup agent

**Produces:** Orchestrator assembling all AI artifacts

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 5.7 (AI dev setup agent).

Create backend/agents/ai_setup.py — AIDevSetupAgent(BaseAgent):

Execution order (instructions.md FIRST, everything else references it):
1. Generate instruction sections → assemble instructions.md
2. Generate skill files (pass instructions.md conventions)
3. Generate hook configs (pass instructions.md conventions)
4. Generate prompt entries
5. Generate tool configs (pass instructions.md content)

Each AIArtifact records: type, filename, content, derived_from, used_default, prompt_version.
Failed skills: log, continue with remaining, inform user.
Update graph/nodes.py.
```

---

## Step 17 — Consistency checker + scaffolding + zip

**Produces:** Validation, project skeleton, downloadable output

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md sections 5.8 (Consistency checker), 5.9 (Scaffolding), 6.5 (Scaffolding skills).

Create:
1. backend/tools/consistency_checker.py (no LLM) — validates artifact consistency
2. backend/skills/scaffolding/generate_folder_structure.py
3. backend/skills/scaffolding/generate_config_file.py
4. backend/skills/scaffolding/generate_pattern_sample.py
5. backend/agents/scaffolder.py — orchestrates scaffolding skills, embeds AI artifacts
6. backend/tools/zip_builder.py (no LLM) — file manifest → .zip archive
7. human_gate_2 in nodes.py

Wire complete graph end-to-end.
```

**Verify:** Full pipeline end-to-end. Upload → parse → review → QA → approve → generate → scaffold → .zip.

---

## Step 18 — FastAPI endpoints

**Produces:** Complete REST API

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 10 (API design).

Create:
1. backend/api/models/ — request/response models
2. backend/api/routes/sessions.py — session CRUD, list for reuse
3. backend/api/routes/documents.py — doc upload, standards upload, standards reuse, coverage check, conflict endpoints
4. backend/api/routes/pipeline.py — start, status, extraction, confirm, review, QA quality, approve, reupload, retry domain, artifacts, scaffolding download, decision log, trace
5. backend/api/routes/websocket.py — real-time updates
6. Update main.py — register routers, SQLite setup

Include conflict resolution endpoint and reviewer retry endpoint.
```

---

## Step 19 — Frontend

**Produces:** Complete React UI

**Prompt:**
```
Read docs/ARCHITECTURE_v2.0.md section 11 (Frontend design).

Create React 18 + Tailwind frontend:

1. UploadView.jsx — project docs + standards upload, coverage indicator, conflict display with resolution, session reuse
2. ExtractionPreview.jsx — ProjectContext verification
3. PipelineView.jsx — stages including QA step, failed stages in red with retry
4. ReviewDashboard.jsx — radar chart, overall + QA quality scores, deduplicated findings, contradiction highlights, low-quality flags
5. ApprovalGate.jsx — per-finding controls, contradiction resolution (choose A or B), override modal, iteration counter
6. GenerationProgress.jsx — per-artifact status, org standard sources, defaults, prompt versions
7. ScaffoldingPreview.jsx — file tree, content preview, download
8. DecisionLog.jsx — timeline with agent, skill, prompt version, standard refs
9. StandardsCoverage.jsx — loaded/missing/conflicting grid

React context + useReducer. WebSocket. Recharts.
```

---

## Step 20 — Demo data + E2E testing

**Produces:** Realistic test scenario proving production readiness

**Prompt:**
```
Create a complete e-commerce demo scenario:

1. tests/demo_data/project_docs/ — brd.md, architecture.md (with intentional gaps: no cache invalidation, no rate limiting, auth token lifecycle missing, no circuit breakers), stories.md, tech-preferences.md

2. tests/demo_data/standards/ — coding-standards.md (camelCase, 2-space indent), security-standards.md (OAuth2+JWT), api-design.md (REST, /v1/ prefix, snake_case for API fields — intentional conflict with coding standard's camelCase), testing-standards.md (80% coverage, Jest)

3. tests/test_e2e/test_full_pipeline.py:
   - Upload all docs + standards
   - Assert: conflict detected between coding camelCase and API snake_case
   - Resolve conflict, proceed
   - Assert: all 5 reviewers produce scored results
   - Assert: security catches missing token lifecycle (references security-standards.md)
   - Assert: QA agent deduplicates overlapping findings
   - Assert: QA detects any contradictions
   - Assert: review quality score produced
   - Approve, generate artifacts
   - Assert: instructions.md includes camelCase rule
   - Assert: sections without org standard marked as defaults
   - Assert: prompt versions recorded on all artifacts
   - Assert: .zip extracts and contains all expected files

4. tests/test_skills/ — individual skill tests for at least:
   - extract_tech_stack with small and large (chunked) input
   - evaluate_dimension with and without org standard
   - deduplicate_findings with known duplicates
   - detect_contradictions with known contradiction
   - generate_instruction_section with and without org standard

5. tests/test_error_handling.py:
   - Simulate skill failure, verify graceful degradation
   - Simulate malformed LLM output, verify retry with error correction
   - Simulate reviewer failure, verify remaining reviewers complete
```

---

## Execution summary

| Step | What | Depends on | Est. time |
|---|---|---|---|
| 1 | Project bootstrap | — | 30 min |
| 2 | Core schemas | 1 | 1.5 hr |
| 3 | Base classes (chunking, retry, versioning) | 2 | 2 hr |
| 4 | Rubric YAMLs | 2 | 30 min |
| 5 | LangGraph skeleton | 2, 3 | 1 hr |
| 6 | Standards loader + conflict detection | 2, 3 | 1 hr |
| 7 | Extraction skills | 3 | 1.5 hr |
| 8 | Document parsing agent | 6, 7 | 1 hr |
| 9 | evaluate-dimension skill | 3 | 1 hr |
| 10 | Five reviewers | 4, 9 | 1 hr |
| 11 | Review aggregator | 10 | 45 min |
| 12 | Review QA agent | 11 | 2 hr |
| 13 | Human gate | 12 | 1 hr |
| 14 | Context synthesis | 13 | 1 hr |
| 15 | Generation skills | 3 | 2 hr |
| 16 | AI dev setup agent | 15 | 1.5 hr |
| 17 | Scaffolding + zip | 16 | 2 hr |
| 18 | FastAPI endpoints | 17 | 2 hr |
| 19 | Frontend | 18 | 3-4 hr |
| 20 | Demo data + E2E | 19 | 2 hr |

**Total: ~25-28 hours with AI coding tools**

---

## Verification checkpoints

| After step | What to verify |
|---|---|
| 5 | Graph compiles and runs with placeholders. LangSmith shows full flow including QA node. |
| 8 | Upload docs → ProjectContext populated. Chunking works on large docs. Conflicts detected. |
| 10 | 5 reviewers run in parallel. Scored results. Org standards influence findings. |
| 12 | QA deduplicates, detects contradictions, produces quality score. |
| 13 | Human gate pauses, resumes with override/accept/revise. Contradiction resolution works. |
| 17 | Full pipeline end-to-end produces downloadable .zip with all artifacts. |
| 20 | E2E test passes. Error handling works. Prompt versions tracked. |

---

## Tips

- **Steps 1-5 are foundation.** Don't rush. If schemas and base classes are solid, everything plugs in.
- **Steps 8+10 are your first demo.** Upload → review with scores. Show this early.
- **Step 12 (QA agent) is the production differentiator.** This is what makes the tool trustworthy for real projects.
- **Step 15-16 (generation) is the value differentiator.** Spend time on prompt templates — they determine output quality.
- **Step 20 tests the intentional conflict** in demo data (camelCase vs snake_case) — this proves conflict detection works end-to-end.
- **Always check LangSmith after each step.** Traces show whether skills are invoked correctly, prompt versions are recorded, and token budgets are respected.
