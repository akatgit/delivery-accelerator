# Architecture & Solution Document v2.0 — Agentic Solution Delivery Accelerator (ASDA)

**Version:** 2.0
**Last updated:** 2026-07-06
**Change log:**
| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-05 | Initial architecture with RAG, monolithic agents |
| 1.5 | 2026-07-06 | RAG removed, org standards direct input, skills/prompts/instructions layered design |
| 2.0 | 2026-07-06 | Production-intent: Review QA Agent, chunking strategy, error handling, prompt versioning, org standard conflict detection |

---

## 1. Solution overview

ASDA is a production-grade multi-agent system built on LangGraph that orchestrates specialized AI agents to review architecture documents against organization engineering standards, validate review quality, and generate AI-ready project scaffolding.

The architecture follows a layered design: agents are thin orchestrators, skills perform focused LLM tasks, prompt templates structure LLM interactions, and instructions provide universal base rules. This separation enables independent testing, reuse, and iteration of each layer.

There is no RAG/vector database. The LLM's built-in knowledge handles public references (OWASP, framework docs). Organization-specific knowledge is provided directly via uploaded standards files. Large documents are handled through map-reduce chunking within skills, not through embedding and retrieval.

## 2. Tech stack

| Layer | Technology | Purpose |
|---|---|---|
| Orchestration | LangGraph | State machine, parallel fan-out, human interrupt gates, state persistence |
| Agent framework | LangChain | LLM chains, structured output parsing, prompt templates, document loaders |
| LLM | Anthropic Claude (claude-sonnet-4-6 via API) | Powers all agents and skills |
| Observability | LangSmith | Tracing, evaluation, token tracking, prompt version tracking |
| Backend API | FastAPI (Python 3.11+) | REST endpoints, file upload, pipeline control |
| Frontend | React + Tailwind CSS | Pipeline visualization, review dashboard, approval workflows |
| State persistence | SQLite | Pipeline checkpointing, session history, org standards reuse |
| File output | Python zipfile + Jinja2 | Scaffolding generation and download |

## 3. System architecture

### 3.1 Pipeline flow

```
Project docs + Org standards
       ↓
[Agent] Document Parsing Agent (with chunking)
       ↓
[Data] ProjectContext → user verification
       ↓
[Agent ×5] Review Board (parallel, org standards routed per domain)
       ↓
[Tool] Review Aggregator (merge, score, sort)
       ↓
[Agent] Review QA Agent (deduplicate, contradictions, validate quality)
       ↓
[Human] Approval Gate ←── revise & re-upload loop
       ↓
[Agent] Context Synthesis Agent
       ↓
[Agent] AI Development Setup Agent (invokes skills per section)
       ↓
[Tool] Consistency Checker
       ↓
[Agent] Project Scaffolding Agent (invokes skills per component)
       ↓
[Human] Approval Gate
       ↓
[Tool] Zip Builder → download
```

### 3.2 Component classification

| Type | Description | LLM interaction |
|---|---|---|
| **Agent** | Thin orchestrator — decides which skills to invoke and in what order. Contains no business logic directly. | Yes — coordinates LLM calls via skills |
| **Skill** | Reusable, testable LLM task. Takes specific inputs, produces specific outputs. Independently testable. Handles its own chunking if inputs are large. | Yes — each skill is a focused LLM call |
| **Prompt template** | Parameterized prompt fragment filled with context at invocation time. Versioned. | Yes — becomes part of the LLM call |
| **Instruction** | Base rules across all agents — output format, severity definitions, component referencing. Loaded into every agent's system prompt. | Indirect — shapes LLM behavior |
| **Tool** | Deterministic logic — no LLM. File parsing, aggregation, consistency checks, zip generation. | None |
| **Data store** | Shared state (ProjectContext) that all agents read/write. Persisted via SQLite checkpointing. | None |
| **Human gate** | Pipeline pause where a human reviews output and makes a decision. | None |

### 3.3 Layered design

```
┌──────────────────────────────────────┐
│         AGENTS (thin orchestrators)  │  Coordinate: decide WHAT skills to call, in WHAT order
├──────────────────────────────────────┤
│         SKILLS (reusable, testable)  │  Execute: perform focused LLM tasks with specific I/O
├──────────────────────────────────────┤
│    PROMPT TEMPLATES (parameterized)  │  Structure: define the shape of each LLM interaction
├──────────────────────────────────────┤
│    INSTRUCTIONS (base rules)         │  Govern: universal rules in every agent's context
├──────────────────────────────────────┤
│    TOOLS (deterministic)             │  Compute: pure logic, no LLM (aggregation, I/O, packaging)
└──────────────────────────────────────┘
```

**Rule:** If it involves an LLM call → skill or prompt template. If it's deterministic → code tool. Agents coordinate; they don't contain logic.

## 4. Production concerns

### 4.1 Chunking strategy

Large documents (exceeding LLM context window) are handled via map-reduce within skills. No external storage or embeddings required.

```
Large document (e.g., 100-page arch doc)
  → RecursiveCharacterTextSplitter (chunk_size=6000 tokens, overlap=500 tokens)
  → Run skill on each chunk (map phase)
  → Merge partial results with deduplication and conflict resolution (reduce phase)
  → Return unified output
```

The chunking logic lives in the BaseSkill class. Each skill defines:
- `max_input_tokens`: threshold above which chunking activates
- `chunk_merge_strategy`: how to combine chunk results ("union" for lists, "merge_and_deduplicate" for structured objects)

Skills that don't need chunking (e.g., generating a single instruction section with a small org standard) skip it entirely.

### 4.2 Error handling

Every LLM call (via skills) has three layers of protection:

**Layer 1 — Output validation:** Every skill output is validated against its Pydantic schema. If the LLM returns malformed JSON or missing fields, the skill retries with an error-correction prompt: "Your previous output was invalid: {validation_error}. Please fix and return valid JSON."

**Layer 2 — Retry logic:** Each skill retries up to 2 times on failure (LLM timeout, rate limit, malformed output). Retries use exponential backoff.

**Layer 3 — Graceful degradation:** If a skill fails after retries, the agent continues with remaining skills. The failed component is logged in `ProjectContext.failed_components` with error details. The user is informed which component failed and can trigger a manual re-run of just that component.

Example: if the security reviewer fails, the other 4 reviewers complete normally. The overall score is recalculated excluding the failed domain. The user sees "Security review failed — click to retry" in the dashboard.

### 4.3 Prompt versioning

Every prompt template has a version identifier (semantic version: `major.minor.patch`).

```
/prompts/templates/review/evaluate_dimension.md
# version: 1.2.0
# last_updated: 2026-07-06
# description: Evaluates a single rubric dimension against project context and org standards
```

When a skill invokes a prompt template, the version is recorded in:
- The decision log entry for that skill invocation
- The `AIArtifact.prompt_version` field for generated artifacts
- The LangSmith trace metadata

This enables: "This instructions.md was generated using prompt v1.2.0 — here's the exact prompt that produced it."

When a prompt template is updated, the version increments. Historical runs remain linked to their original prompt version.

### 4.4 Org standard conflict detection

Before the pipeline starts, a deterministic tool scans all uploaded org standards for potential conflicts using an LLM-powered skill:

```
Input: all org standard contents
Skill: detect-standard-conflicts
Output: list[StandardConflict] — each with category_a, statement_a, category_b, statement_b, description
```

Examples of detectable conflicts:
- Coding standard says "camelCase for all identifiers" but API design says "snake_case for request fields"
- Security standard says "log all API requests" but logging standard says "never log request bodies"
- Testing standard says "80% coverage" but organization practices says "100% coverage for critical paths"

Conflicts are surfaced to the user before the pipeline starts. User must resolve (update a standard) or acknowledge (accept the conflict, noting which standard takes priority). Resolved/acknowledged conflicts inform downstream agents.

### 4.5 Context window management

Each skill manages its context budget:

| Budget allocation | Percentage |
|---|---|
| System prompt + instructions | ~15% |
| Prompt template | ~10% |
| Org standards (routed) | ~25% |
| Project context (relevant sections) | ~35% |
| Output space | ~15% |

Skills that receive multiple org standards (e.g., testing-standards routed to all reviewers) may need to summarize rather than pass full content. The skill detects when total input exceeds budget and triggers summarization of the least-critical inputs.

## 5. Component design

### 5.1 Document parsing agent

| Property | Value |
|---|---|
| **Type** | Agent (thin orchestrator) |
| **LLM interaction** | Yes — invokes extraction skills |
| **Input** | Raw markdown/text files (project docs + org standards) |
| **Output** | Populated ProjectContext |
| **Skills invoked** | `extract-tech-stack`, `extract-components`, `extract-nfrs`, `extract-stories`, `identify-gaps`, `detect-standard-conflicts` |

Orchestrates extraction in sequence (each step receives accumulated context):
1. Load and categorize org standards (deterministic — standards_loader tool)
2. Detect conflicts between org standards (LLM skill)
3. `extract-tech-stack` on tech preferences + arch doc
4. `extract-components` on arch doc (with tech stack context)
5. `extract-nfrs` on BRD (with components context)
6. `extract-stories` on stories doc (with components context)
7. `identify-gaps` across all extracted data

Large documents trigger map-reduce chunking within each extraction skill.

### 5.2 Review board — five reviewer agents

| Property | Value |
|---|---|
| **Type** | Agent ×5 (parallel) |
| **LLM interaction** | Yes — invokes `evaluate-dimension` skill per rubric dimension |
| **Input** | ProjectContext + routed org standards + rubric |
| **Output** | ReviewResult per domain |
| **Execution** | Parallel via LangGraph `Send()` |

All five share the same execution pattern (defined in BaseReviewer):
1. Load rubric YAML
2. Extract relevant org standards based on `org_standard_categories` config
3. For each rubric dimension → invoke `evaluate-dimension` skill
4. Aggregate dimension scores → compute domain score
5. Return ReviewResult

**Org standard routing:**

| Reviewer | Receives |
|---|---|
| Architecture | coding, api-design, naming, repository-conventions |
| Security | security, api-design |
| Performance | api-design, logging |
| Reliability | logging, exception-handling, testing |
| Compliance | cicd, organization-practices |

All also receive organization-practices if provided.

**Error handling:** If a reviewer fails after retries, remaining reviewers continue. Failed domain excluded from overall score. User can retry the failed domain independently.

### 5.3 Review aggregator

| Property | Value |
|---|---|
| **Type** | Tool (deterministic, no LLM) |
| **Input** | List of ReviewResults (from completed reviewers) |
| **Output** | Merged findings, overall weighted score, remediation summary |

Pure logic: merge results, sort findings by severity, compute weighted score (excluding failed domains), generate remediation summary.

### 5.4 Review QA agent

| Property | Value |
|---|---|
| **Type** | Agent |
| **LLM interaction** | Yes — uses LLM for semantic analysis of review output |
| **Input** | Aggregated review results + ProjectContext |
| **Output** | ReviewQAResult (quality score, duplicates, contradictions, normalizations, warnings) |
| **Skills invoked** | `deduplicate-findings`, `detect-contradictions`, `validate-actionability`, `check-coverage` |

This agent validates the quality of the review output before it reaches the human. It does not override scores or add findings — it validates quality, not correctness.

**Skill: deduplicate-findings**
- Input: all findings across all domains
- LLM analyzes semantic similarity (not string matching) — "missing rate limiting" and "no API throttling" are the same issue
- Output: list of duplicate pairs with merge recommendation
- Merged findings preserve the higher severity and cite contributing domains

**Skill: detect-contradictions**
- Input: all findings and recommendations
- LLM identifies cases where reviewers recommend opposing approaches
- Output: list of contradictions with both positions and context
- Contradictions are flagged for human resolution — QA agent does not pick a winner

**Skill: validate-actionability**
- Input: all findings + ProjectContext.components
- LLM checks: does each finding reference real component names? Is the recommendation specific to the tech stack or generic filler?
- Output: list of low-quality finding IDs with reasons

**Skill: check-coverage**
- Input: all ReviewResults + ProjectContext (component count, architecture style)
- LLM evaluates: is it suspicious that a reviewer returned zero findings for a complex architecture?
- Output: list of coverage warnings

**Review quality score:** Computed from deduplication ratio (fewer duplicates = better individual review quality), contradiction count (fewer = more consistent), actionability rate (higher = better), coverage completeness. Score of 1-10 shown to the human alongside the review.

### 5.5 Human approval gate

| Property | Value |
|---|---|
| **Type** | Human gate |
| **LLM interaction** | No |
| **Implementation** | LangGraph `interrupt()` |

Presents QA-validated review to user. Three actions: accept, override (per finding or per domain), revise & re-upload. Additionally, for contradictions flagged by QA: user must choose which recommendation to follow.

### 5.6 Context synthesis agent

| Property | Value |
|---|---|
| **Type** | Agent |
| **LLM interaction** | Yes |
| **Skills invoked** | `identify-patterns`, `plan-artifact-generation` |

Bridges review and generation. Reads approved context (including contradiction resolutions) and determines which patterns and artifacts to generate.

### 5.7 AI development setup agent

| Property | Value |
|---|---|
| **Type** | Agent (thin orchestrator) |
| **LLM interaction** | Yes — invokes generation skills per artifact section |
| **Skills invoked** | `generate-instruction-section`, `generate-skill-file`, `generate-hook-config`, `generate-prompt-entry`, `generate-tool-config` |

Execution flow:
1. Generate instructions.md sections (one skill call per standard category) — **must complete first**
2. Generate skill files (one per pattern) — references instructions.md
3. Generate hook configs (one per hook type) — references instructions.md
4. Generate prompt library entries (one per category) — references instructions.md
5. Generate tool configs (one per AI tool) — references instructions.md

Each skill invocation records its prompt version for traceability.

**Default handling:** Missing org standard → skill generates from LLM best practices + marks output with warning. `AIArtifact.used_default = true`.

**Contradiction handling:** Where contradictions were resolved by the human (choosing one recommendation over another), the chosen approach is enforced in generated artifacts. The unchosen approach is excluded.

### 5.8 Consistency checker

| Property | Value |
|---|---|
| **Type** | Tool (deterministic, no LLM) |
| **Input** | All generated AIArtifacts + org_standards |
| **Output** | List of inconsistency warnings |

Validates: naming conventions in skills match instructions.md, hook lint rules align with coding standards, PR template items trace to review rubric. Inconsistencies flagged to user (not blocking).

### 5.9 Project scaffolding agent

| Property | Value |
|---|---|
| **Type** | Agent |
| **LLM interaction** | Yes |
| **Skills invoked** | `generate-folder-structure`, `generate-config-file`, `generate-pattern-sample` |

Generates project skeleton, embeds AI artifacts, produces README. Outputs file manifest → zip builder creates .zip.

### 5.10 Second human approval gate

Same as 5.5. User reviews scaffolding in file tree preview.

## 6. Skills catalog

### 6.1 Extraction skills

| Skill | Input | Output | Chunking |
|---|---|---|---|
| `extract-tech-stack` | Tech prefs + arch doc | list[TechStackItem] | Yes if doc large |
| `extract-components` | Arch doc + tech stack | list[Component] | Yes if doc large |
| `extract-nfrs` | BRD + components | list[NFR] | Yes if doc large |
| `extract-stories` | Stories + components | list[Story] | Yes if doc large |
| `identify-gaps` | Full ProjectContext | list[Gap] | No (input is structured) |
| `detect-standard-conflicts` | All org standard contents | list[StandardConflict] | No (standards are small) |

### 6.2 Review skills

| Skill | Input | Output | Chunking |
|---|---|---|---|
| `evaluate-dimension` | Dimension criteria + ProjectContext + org standard + scoring anchors | DimensionScore | No (context pre-selected) |

### 6.3 QA skills

| Skill | Input | Output | Chunking |
|---|---|---|---|
| `deduplicate-findings` | All findings across domains | Duplicate pairs + merge recommendations | No |
| `detect-contradictions` | All findings and recommendations | Contradiction list | No |
| `validate-actionability` | All findings + component names | Low-quality finding IDs | No |
| `check-coverage` | ReviewResults + architecture complexity | Coverage warnings | No |

### 6.4 Generation skills

| Skill | Input | Output | Chunking |
|---|---|---|---|
| `generate-instruction-section` | Category + org standard + findings + context | Section markdown | No |
| `generate-skill-file` | Pattern + components + standards + conventions | Skill file content | No |
| `generate-hook-config` | Hook type + standards + conventions | Hook config content | No |
| `generate-prompt-entry` | Category + tech stack + conventions | Prompt content | No |
| `generate-tool-config` | Tool template + instructions.md + context | Tool config content | No |

### 6.5 Scaffolding skills

| Skill | Input | Output | Chunking |
|---|---|---|---|
| `generate-folder-structure` | Components + tech stack + existing codebase | Directory tree dict | No |
| `generate-config-file` | Config type + standards + tech stack | Config file content | No |
| `generate-pattern-sample` | Pattern + standards + conventions | Implementation + test + header | No |

**Total: 19 distinct skills.** Each independently testable with defined input/output contracts.

## 7. Prompt templates

### 7.1 Template structure

Each template defines: system context, parameters (filled at invocation), output schema, and version metadata.

```
# version: 1.0.0
# skill: evaluate-dimension

SYSTEM:
You are evaluating the "{dimension_name}" dimension of a software architecture.

SCORING ANCHORS:
{scoring_anchors}

DIMENSION CRITERIA:
{dimension_description}

PROJECT CONTEXT:
{project_context_excerpt}

{%if org_standard %}
ORGANIZATION STANDARD:
{org_standard_content}
CRITICAL: Evaluate compliance with this standard. Do not contradict it.
{%else%}
No organization standard provided. Evaluate against general best practices.
{%endif%}

{%if accepted_findings %}
PREVIOUSLY ACCEPTED FINDINGS for this dimension:
{accepted_findings}
{%endif%}

OUTPUT (JSON):
{output_schema}
```

### 7.2 Version management

Templates stored as files with version headers. Version recorded in every skill invocation, decision log entry, and generated artifact. When a template is updated, version increments. Historical runs remain linked to original versions.

## 8. Instructions — base rules

Loaded into every agent's system prompt:

```
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
```

## 9. LangGraph state machine

### 9.1 Graph definition

```
START
  → parse_documents
  → detect_standard_conflicts (if conflicts → pause for user resolution)
  → route_to_reviewers (Send() → 5 parallel nodes)
    → architecture_reviewer  ─┐
    → security_reviewer      ─┤
    → performance_reviewer   ─┤
    → reliability_reviewer   ─┤
    → compliance_reviewer    ─┘
  → aggregate_reviews
  → review_qa_agent
  → human_gate_1 (interrupt)
    → if REVISE → parse_documents
    → if ACCEPT/OVERRIDE → continue
  → synthesize_context
  → generate_ai_artifacts
  → consistency_check
  → generate_scaffolding
  → human_gate_2 (interrupt)
    → if REJECT → synthesize_context
    → if ACCEPT → continue
  → build_zip
  → END
```

### 9.2 State persistence

```python
from langgraph.checkpoint.sqlite import SqliteSaver

checkpointer = SqliteSaver.from_conn_string("./pipeline_state.db")
graph = builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_gate_1", "human_gate_2"]
)
```

### 9.3 Human interrupt flow

```python
result = graph.invoke(initial_state, config={"thread_id": session_id})
# result.next == "human_gate_1" — paused

# User reviews and decides
graph.invoke(
    Command(resume={
        "decision": "accept",
        "overrides": [...],
        "contradiction_resolutions": [...]
    }),
    config={"thread_id": session_id}
)
```

## 10. API design

### 10.1 Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/sessions` | Create session |
| GET | `/api/sessions` | List sessions (for standards reuse) |
| GET | `/api/sessions/{id}` | Session details + stage |
| POST | `/api/sessions/{id}/documents` | Upload project docs |
| POST | `/api/sessions/{id}/standards` | Upload org standards |
| POST | `/api/sessions/{id}/standards/reuse/{source_id}` | Reuse from previous session |
| GET | `/api/sessions/{id}/standards/coverage` | Missing categories check |
| GET | `/api/sessions/{id}/standards/conflicts` | Detected conflicts |
| POST | `/api/sessions/{id}/standards/conflicts/resolve` | Resolve/acknowledge conflicts |
| POST | `/api/sessions/{id}/start` | Start pipeline |
| GET | `/api/sessions/{id}/status` | Current stage + progress |
| GET | `/api/sessions/{id}/extraction` | Parsed ProjectContext |
| POST | `/api/sessions/{id}/extraction/confirm` | Confirm extraction |
| GET | `/api/sessions/{id}/review` | QA-validated review report |
| GET | `/api/sessions/{id}/review/quality` | Review QA score + details |
| POST | `/api/sessions/{id}/approve` | Human gate decision |
| POST | `/api/sessions/{id}/reupload` | Revised docs for re-review |
| POST | `/api/sessions/{id}/retry/{domain}` | Retry a failed reviewer |
| GET | `/api/sessions/{id}/artifacts` | Preview generated artifacts |
| GET | `/api/sessions/{id}/scaffolding` | Download .zip |
| GET | `/api/sessions/{id}/decision-log` | Full decision log |
| GET | `/api/sessions/{id}/trace` | LangSmith trace URL |

### 10.2 WebSocket

`ws://api/sessions/{id}/stream` — real-time updates: stage transitions, reviewer completions, QA progress, scores, errors.

## 11. Frontend design

### 11.1 Views

**UploadView** — Project docs + standards upload. Standards coverage indicator. Conflict display with resolution controls. Session reuse dropdown.

**ExtractionPreview** — Parsed ProjectContext verification. Tech stack, components, NFRs, stories, gaps.

**PipelineView** — Stage indicator: Upload → Parse → Review → QA → Approve → Generate → Scaffold → Deliver. Failed stages shown in red with retry button.

**ReviewDashboard** — Radar chart of domain scores. Overall score + review quality score. QA-validated findings: deduplicated, contradictions highlighted, low-quality findings flagged. Per-finding accept/override.

**ApprovalGate** — Finding action controls. Contradiction resolution (choose recommendation A or B with rationale). Override justification modal. Iteration counter.

**GenerationProgress** — Per-artifact generation status. Org standard sources per artifact. Default warnings. Prompt versions used.

**ScaffoldingPreview** — File tree, content preview, AI artifact badges. Download button.

**DecisionLog** — Timeline with agent, skill, prompt version, decision, rationale, standard references.

**StandardsCoverage** — Grid showing loaded/missing/conflicting categories.

### 11.2 Tech

React 18, Tailwind CSS, React context + useReducer, WebSocket, Recharts.

## 12. Component interaction matrix

| Component | Type | LLM | Org standards | Reads context | Writes context |
|---|---|---|---|---|---|
| Document parsing agent | Agent | Yes (skills) | Loads + categorizes | Creates it | All extracted fields |
| Standard conflict detector | Skill | Yes | All (to compare) | No | org_standards.conflicts |
| Architecture reviewer | Agent | Yes (skills) | coding, api-design, naming, repo | components, NFRs, stack | ReviewResult |
| Security reviewer | Agent | Yes (skills) | security, api-design | components, stack | ReviewResult |
| Performance reviewer | Agent | Yes (skills) | api-design, logging | components, NFRs | ReviewResult |
| Reliability reviewer | Agent | Yes (skills) | logging, exception, testing | components, NFRs | ReviewResult |
| Compliance reviewer | Agent | Yes (skills) | cicd, org-practices | NFRs, data entities | ReviewResult |
| Review aggregator | Tool | No | No | All ReviewResults | overall_score, remediation |
| Review QA agent | Agent | Yes (skills) | No | All findings + components | review_qa |
| Human gate | Human | No | No | Review report + QA | human_decisions |
| Context synthesis | Agent | Yes (skills) | All (plan generation) | Full approved context | patterns, plan |
| AI dev setup | Agent | Yes (skills) | All (routed per section) | Full context + findings | ai_artifacts |
| Consistency checker | Tool | No | Yes (validation) | ai_artifacts | No (flags to UI) |
| Scaffolding agent | Agent | Yes (skills) | cicd, repo-conventions | Full context + artifacts | scaffolding_structure |
| Zip builder | Tool | No | No | scaffolding_structure | File output |

## 13. Token strategy

| Component | Tokens (input+output) | LLM calls | Notes |
|---|---|---|---|
| Extraction skills (5) | ~3K+1K each | 5 | Sequential, chunked if large |
| Conflict detection | ~4K+1K | 1 | All standards in one call |
| evaluate-dimension | ~3K+1K each | ~25 (5×5) | Parallel across reviewers |
| QA skills (4) | ~4K+1K each | 4 | After aggregation |
| Context synthesis (2) | ~4K+1K each | 2 | |
| Instruction sections | ~3K+1K each | ~10 | One per category |
| Skill files | ~3K+2K each | ~7 | One per pattern |
| Hook configs | ~2K+1K each | ~5 | |
| Prompt entries | ~2K+1K each | ~7 | |
| Tool configs | ~3K+1K each | ~3 | |
| Scaffolding skills | ~4K+2K each | ~5 | |

**Total: ~120K-160K tokens across ~75-80 LLM calls.** ~$0.35-0.50 per run.

Skills-based approach advantages: small focused calls, cacheable, individually retriable, predictable token budgets, traceable in LangSmith per skill.

## 14. Project structure

```
asda/
├── README.md
├── docs/
│   ├── BRD_v2.0.md
│   └── ARCHITECTURE_v2.0.md
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── sessions.py
│   │   │   ├── documents.py
│   │   │   ├── pipeline.py
│   │   │   └── websocket.py
│   │   └── models/
│   ├── agents/
│   │   ├── base.py
│   │   ├── document_parser.py
│   │   ├── context_synthesizer.py
│   │   ├── ai_setup.py
│   │   ├── scaffolder.py
│   │   ├── review_qa.py
│   │   └── reviewers/
│   │       ├── base_reviewer.py
│   │       ├── architecture.py
│   │       ├── security.py
│   │       ├── performance.py
│   │       ├── reliability.py
│   │       └── compliance.py
│   ├── skills/
│   │   ├── base.py                    # BaseSkill with chunking + retry + validation
│   │   ├── extraction/
│   │   │   ├── extract_tech_stack.py
│   │   │   ├── extract_components.py
│   │   │   ├── extract_nfrs.py
│   │   │   ├── extract_stories.py
│   │   │   ├── identify_gaps.py
│   │   │   └── detect_standard_conflicts.py
│   │   ├── review/
│   │   │   └── evaluate_dimension.py
│   │   ├── qa/
│   │   │   ├── deduplicate_findings.py
│   │   │   ├── detect_contradictions.py
│   │   │   ├── validate_actionability.py
│   │   │   └── check_coverage.py
│   │   ├── generation/
│   │   │   ├── identify_patterns.py
│   │   │   ├── plan_artifact_generation.py
│   │   │   ├── generate_instruction_section.py
│   │   │   ├── generate_skill_file.py
│   │   │   ├── generate_hook_config.py
│   │   │   ├── generate_prompt_entry.py
│   │   │   └── generate_tool_config.py
│   │   └── scaffolding/
│   │       ├── generate_folder_structure.py
│   │       ├── generate_config_file.py
│   │       └── generate_pattern_sample.py
│   ├── prompts/
│   │   ├── templates/                 # Versioned prompt templates
│   │   │   ├── extraction/
│   │   │   ├── review/
│   │   │   ├── qa/
│   │   │   └── generation/
│   │   └── instructions/
│   │       └── base_rules.md
│   ├── graph/
│   │   ├── pipeline.py
│   │   ├── state.py
│   │   └── nodes.py
│   ├── schemas/
│   │   ├── project_context.py
│   │   ├── review.py
│   │   ├── review_qa.py
│   │   ├── org_standards.py
│   │   ├── artifacts.py
│   │   └── pipeline.py
│   ├── rubrics/
│   │   ├── architecture.yaml
│   │   ├── security.yaml
│   │   ├── performance.yaml
│   │   ├── reliability.yaml
│   │   ├── compliance.yaml
│   │   └── loader.py
│   ├── templates/
│   │   ├── scaffolding/
│   │   │   ├── dockerfile.j2
│   │   │   ├── docker-compose.j2
│   │   │   ├── github-actions.j2
│   │   │   └── readme.j2
│   │   └── tools/
│   │       ├── cursorrules.j2
│   │       ├── copilot-instructions.j2
│   │       └── slingshot-config.j2
│   └── tools/
│       ├── aggregator.py
│       ├── consistency_checker.py
│       ├── standards_loader.py
│       └── zip_builder.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── UploadView.jsx
│   │   │   ├── ExtractionPreview.jsx
│   │   │   ├── PipelineView.jsx
│   │   │   ├── ReviewDashboard.jsx
│   │   │   ├── ApprovalGate.jsx
│   │   │   ├── GenerationProgress.jsx
│   │   │   ├── ScaffoldingPreview.jsx
│   │   │   ├── DecisionLog.jsx
│   │   │   └── StandardsCoverage.jsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.js
│   │   └── context/
│   │       └── SessionContext.jsx
│   └── package.json
├── tests/
│   ├── test_skills/
│   ├── test_agents/
│   ├── test_graph/
│   ├── test_api/
│   └── demo_data/
├── pyproject.toml
└── docker-compose.yml
```

## 15. Extensibility

**New reviewer:** YAML rubric + agent config. No pipeline changes.
**New AI tool config:** Template in /templates/tools/ + registration.
**New document format (Phase 2):** New LangChain document loader. Skills unchanged.
**New standard category:** Add to recognized list + routing table.
**New QA check:** New skill in /skills/qa/ + invocation in review_qa agent.

## 16. Decision log specification

```python
class DecisionEntry(BaseModel):
    timestamp: str
    agent: str
    skill: str | None
    prompt_version: str | None
    decision: str
    rationale: str
    alternatives_considered: list[str]
    context_refs: list[str]
    standard_refs: list[str]
```

Every agent and skill invocation, every human action appends to this log. LangSmith trace spans correlate to decision log entries via skill name + timestamp.
