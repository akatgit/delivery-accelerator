# Business Requirements Document v2.0 — Agentic Solution Delivery Accelerator (ASDA)

**Version:** 2.0
**Last updated:** 2026-07-06
**Change log:**
| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-07-05 | Initial BRD with 10 review findings incorporated |
| 1.5 | 2026-07-06 | RAG removed, org standards as direct input, skills/prompts/instructions layered design, context-aware generation, phase 2 memory |
| 2.0 | 2026-07-06 | Production-intent updates: Review QA Agent, chunking strategy, error handling, prompt versioning, org standard conflict detection |

---

## 1. Executive summary

The Agentic Solution Delivery Accelerator is a multi-agent AI system that consumes existing project artifacts (BRD, architecture documents, user stories) and organization engineering standards, performs automated multi-dimensional quality reviews with quality assurance validation, and generates an AI-ready project scaffolding — complete with coding conventions, skills, hooks, and prompt libraries — so that every developer on the team works with AI coding assistants under the same standards and guardrails.

The system is designed for production use across real projects. It is reusable — organization standards persist across sessions, and the system handles real-world document sizes, edge cases, and failure scenarios gracefully.

## 2. Problem statement

Modern delivery teams face three compounding problems:

**Problem 1 — Architecture review is slow and inconsistent.** Reviews depend on whoever is available, what they remember to check, and how much time they have. Security gaps, performance bottlenecks, and compliance risks slip through because no single reviewer covers every dimension systematically.

**Problem 2 — AI coding assistants amplify inconsistency.** When developers use Cursor, Copilot, Slingshot, or similar tools without shared conventions, each developer gets different patterns, naming styles, and architectural approaches from the AI. The codebase diverges fast. Teams need shared AI guardrails (instruction files, skills, hooks) but creating them manually is tedious and rarely done.

**Problem 3 — Engineering standards exist but don't reach the code.** Organizations maintain coding standards, security guidelines, API conventions, and testing strategies in documents that developers read once and forget. There is no mechanism to automatically translate these standards into executable AI development rules that every coding assistant follows.

## 3. Target users

| User | Role in the system | Key need |
|---|---|---|
| **Tech lead / Architect** | Uploads project docs and org standards, reviews findings, approves scaffolding | Fast, structured feedback on architecture quality; consistent team setup |
| **Delivery manager** | Views review scores, tracks remediation | Confidence that quality gates were passed |
| **Developer** | Consumes the generated scaffolding and AI artifacts | Consistent AI-assisted coding from day one, regardless of which AI tool they use |

## 4. Goals

- Provide structured, scored architecture reviews across security, performance, reliability, compliance, and architecture quality dimensions.
- Validate review quality before presenting to the human — deduplicate, resolve contradictions, normalize severity, and detect gaps in review coverage.
- Generate AI development artifacts (instructions, skills, hooks, prompts) by synthesizing project context, approved architectural decisions, and organization engineering standards — creating a single source of truth for all developers and AI coding assistants.
- Ensure that regardless of whether a developer uses Slingshot, Cursor, Copilot, or another AI tool, they all receive consistent project-specific guidance aligned with the approved architecture and org standards.
- Support a human-in-the-loop approval workflow with the ability to accept, override, or revise and re-submit.
- Handle real-world document sizes (100+ pages) through intelligent chunking without losing context.
- Produce a full audit trail — every decision, score, override, and prompt version is logged and traceable.
- Be reusable across projects — upload new project docs, reuse org standards, generate a fresh scaffolding.

## 5. Scope

### 5.1 In scope (MVP — see section 15 for phasing)

- Accept uploaded project documents: BRD/PRD, architecture documents, user stories, tech stack preferences (markdown or text format).
- Accept uploaded organization engineering standards: coding guidelines, security standards, naming conventions, logging standards, exception handling standards, API design guidelines, testing standards, CI/CD standards, repository conventions (markdown or text format, organized in a /standards folder with descriptive filenames).
- Detect and surface conflicts between org standards (e.g., naming convention in coding standard contradicts naming in API design standard).
- Accept an optional existing codebase reference (Git repository URL or uploaded project structure summary) to inform scaffolding around existing code.
- Document parsing and structured extraction into the normalized ProjectContext schema (defined in section 12) with intelligent chunking for large documents.
- Multi-agent parallel review across five domains: architecture, security, performance, reliability, compliance. Reviewers use the relevant org standards + LLM knowledge to evaluate the architecture.
- Review quality assurance: an LLM-powered QA agent validates review output before presenting to the human — deduplicates findings, detects contradictions, normalizes severity, validates actionability, and checks review completeness.
- Scored review output using explicit rubrics (defined in section 13) with severity-classified findings.
- Consolidated, QA-validated review report with prioritized remediation items.
- Human approval gate with per-finding accept / override with justification / revise & re-upload flow.
- Partial re-review on re-upload (only re-run reviewers with open findings).
- Context-aware AI development setup generation: the system synthesizes project context + accepted review findings + org standards to generate instructions.md, skills/, hooks/, prompt library, and tool-specific configs.
- Project scaffolding generation: folder structure, boilerplate, CI/CD configs, sample pattern implementations — output as a downloadable .zip archive.
- Session persistence: org standards from previous sessions can be reused without re-uploading.
- Decision log capturing every agent's reasoning, prompt versions used, and every human override.
- LangSmith observability across the full pipeline.
- Production-grade error handling: graceful degradation when individual skills fail, retry logic, output validation.

### 5.2 Out of scope

- Architecture document generation from scratch (we consume, not create).
- User story generation from scratch.
- Code generation beyond scaffolding and pattern samples.
- Deployment or infrastructure provisioning.
- Integration with external project management tools (Jira, Azure DevOps).
- Real-time collaboration or multi-user concurrent editing.
- Support for non-English documents (initial release).
- Enterprise-grade authentication, multi-tenancy, and RBAC.
- RAG/vector database — the LLM's built-in knowledge handles public framework docs, OWASP, and best practices. Org-specific knowledge is provided directly via uploaded standards.

## 6. Functional requirements

### FR-1: Document upload and ingestion

| ID | Requirement |
|---|---|
| FR-1.1 | System shall accept markdown (.md) and text (.txt) files as input documents. |
| FR-1.2 | System shall accept multiple project documents per session: BRD, architecture doc, stories, tech preferences. Each document type is tagged on upload. |
| FR-1.3 | System shall accept organization engineering standards uploaded to a /standards folder (or equivalent UI section). Standards are identified by filename or subfolder (e.g., `security-standards.md`, `coding-guidelines.md`). |
| FR-1.4 | System shall recognize the following standard categories based on filename/tag: coding, security, api-design, naming, logging, exception-handling, testing, cicd, repository-conventions, organization-practices. Unrecognized files are accepted and classified as "general" standards. |
| FR-1.5 | System shall detect conflicts between uploaded org standards (e.g., naming convention in coding-standards contradicts naming in api-design). Conflicts are surfaced to the user with both conflicting statements and the source files. User must resolve or acknowledge conflicts before proceeding. |
| FR-1.6 | System shall accept an optional existing codebase input — either a Git repository URL (for structure-only analysis) or an uploaded project structure summary. |
| FR-1.7 | System shall extract structured data from uploaded project documents into the ProjectContext schema (section 12). For documents exceeding the LLM context window, the system uses map-reduce chunking — splitting the document, extracting from each chunk, and merging results with deduplication and conflict resolution. Extraction output shall be shown to the user for verification before proceeding. |
| FR-1.8 | System shall identify and flag gaps or ambiguities in uploaded documents. Gaps are classified as critical (blocks review), major (reviewers will flag it), or informational. |
| FR-1.9 | System shall detect which standard categories are missing by comparing uploaded files against expected categories. For each missing category, the system displays a warning. User can proceed or upload the missing standard. |
| FR-1.10 | System shall support re-upload of revised documents, carrying forward existing review state. On re-upload, the system diffs the new extraction against the previous one and highlights what changed. |
| FR-1.11 | System shall allow reuse of org standards from a previous session. On the upload screen, user can select "reuse standards from session X" instead of re-uploading. |

### FR-2: Architecture review

| ID | Requirement |
|---|---|
| FR-2.1 | System shall execute five review agents in parallel: architecture, security, performance, reliability, compliance. |
| FR-2.2 | Each reviewer shall receive: the ProjectContext, the relevant org standards for its domain (routed by category tag), and the review rubric. The reviewer uses these inputs plus LLM built-in knowledge to evaluate the architecture. |
| FR-2.3 | Each reviewer shall score the architecture using the explicit rubric defined in section 13. Each rubric dimension receives a score of 1–10 with anchored definitions. |
| FR-2.4 | Each reviewer shall produce specific findings with severity classification: critical, major, minor, suggestion. |
| FR-2.5 | Each finding shall include: a title, description of the issue, affected components (referencing ProjectContext.components by name), an actionable recommendation, and the org standard or best practice that the recommendation is based on. |
| FR-2.6 | System shall produce a consolidated review report aggregating all reviewer outputs, sorted by severity. |
| FR-2.7 | System shall compute an overall weighted score: architecture (25%), security (25%), performance (20%), reliability (20%), compliance (10%). |
| FR-2.8 | A minimum overall score of 6.0 is required to proceed to generation. Below 6.0, the system recommends revision before proceeding (user can override). |
| FR-2.9 | If a reviewer skill fails (LLM error, timeout, malformed output), the system shall retry up to 2 times. If the reviewer still fails, the pipeline continues with the remaining reviewers, flags the failed domain, and excludes it from the overall score calculation. The user is informed which domain failed and can trigger a manual re-run. |

### FR-2.10: Review quality assurance

| ID | Requirement |
|---|---|
| FR-2.10.1 | After all reviewers complete and results are aggregated, the system shall run a Review QA Agent that validates the quality and consistency of the review output before presenting it to the human. |
| FR-2.10.2 | **Semantic deduplication:** The QA agent shall identify findings across different reviewers that describe the same underlying issue (e.g., "missing rate limiting" from security and "no API throttling" from performance). Duplicates are merged into a single finding citing both domains, with the higher severity preserved. |
| FR-2.10.3 | **Contradiction detection:** The QA agent shall identify cases where two reviewers make opposing recommendations (e.g., security says "add auth at gateway" while architecture says "keep gateway stateless"). Contradictions are flagged with both positions and context so the human can decide. The QA agent does not resolve contradictions — it surfaces them. |
| FR-2.10.4 | **Severity normalization:** When the same issue is rated at different severities by different reviewers, the QA agent escalates to the higher severity and adds a note explaining the discrepancy. |
| FR-2.10.5 | **Actionability validation:** The QA agent checks that each finding has non-empty affected_components that match actual component names in the ProjectContext, and that recommendations are specific to the project's tech stack (not generic advice like "improve security"). Findings that fail this check are flagged as low-quality with a note to the reviewer domain. |
| FR-2.10.6 | **Coverage check:** The QA agent verifies that each reviewer produced at least one finding for architectures with known complexity indicators (>5 components, microservices, distributed systems). A reviewer returning zero findings for a complex architecture is flagged as suspicious with a recommendation to re-run. |
| FR-2.10.7 | **Review quality score:** The QA agent produces a review quality score (1-10) reflecting: deduplication ratio, contradiction count, actionability rate, and coverage completeness. This score is shown to the human alongside the review to indicate confidence in the review output. |
| FR-2.10.8 | The QA agent shall not override reviewer scores, add new findings, or second-guess domain expertise. It validates quality, not correctness. |

### FR-3: Human approval gate

| ID | Requirement |
|---|---|
| FR-3.1 | System shall pause the pipeline and present the QA-validated consolidated review to the user, showing: overall score, per-domain scores, review quality score, all findings (deduplicated, with contradictions flagged), grouped by severity, and the minimum score threshold status. |
| FR-3.2 | **Accept all:** User accepts all findings as acknowledged and the pipeline proceeds. |
| FR-3.3 | **Override per finding:** User can override individual findings. Each override requires a written justification (minimum 20 characters). Critical findings require additional confirmation. Overridden findings are excluded from artifact generation. |
| FR-3.4 | **Override per domain:** User can override an entire domain's findings in bulk with a single justification. |
| FR-3.5 | **Revise & re-upload:** User uploads revised documents. System re-runs only reviewers whose domains had open findings of severity major or critical. Minor and suggestion findings carry forward. |
| FR-3.6 | **Contradiction resolution:** For flagged contradictions, the human must explicitly choose which recommendation to follow. The unchosen recommendation is logged as "resolved — alternative chosen" with the human's rationale. |
| FR-3.7 | After override or accept, downstream agents receive the findings and their statuses. Accepted findings inform artifact generation. Overridden findings are excluded. |
| FR-3.8 | All human decisions shall be logged with timestamps, justification, and finding IDs. |
| FR-3.9 | Maximum 5 review-revise iterations per session. |

### FR-4: Context-aware AI development setup generation

| ID | Requirement |
|---|---|
| FR-4.1 | The AI Development Setup Agent shall generate artifacts by synthesizing four input sources: (1) ProjectContext, (2) accepted review findings and approved decisions (including contradiction resolutions), (3) organization engineering standards, (4) tool-specific configuration templates. |
| FR-4.2 | Only approved decisions and accepted findings shall influence artifacts. Overridden findings shall not be enforced. |
| FR-4.3 | Where an org standard is provided, artifacts follow it precisely. Where missing, the system uses LLM best practices and marks sections with a default warning. |
| FR-4.4 | The agent shall operate as a thin orchestrator, invoking reusable skills and prompt templates per artifact section. |
| FR-4.5 | Each skill invocation shall record the prompt version used, enabling traceability from artifact output back to the exact prompt that produced it. |

#### FR-4.6: instructions.md generation

| ID | Requirement |
|---|---|
| FR-4.6.1 | System shall generate instructions.md defining project-wide engineering standards: architecture principles, folder structure, layer responsibilities, coding standards, naming conventions, API design conventions, logging standards, exception handling strategy, validation rules, security guidelines, testing strategy, documentation requirements. |
| FR-4.6.2 | Each section generated by invoking "generate-instruction-section" skill with: category, org standard content (if provided), accepted findings, project context. |
| FR-4.6.3 | Accepted review findings reflected as explicit rules. Contradiction resolutions reflected with the chosen approach. |

#### FR-4.7: Skills generation

| ID | Requirement |
|---|---|
| FR-4.7.1 | System shall generate skill files — reusable AI task definitions for common engineering activities. |
| FR-4.7.2 | Each skill generated by invoking "generate-skill-file" skill. |
| FR-4.7.3 | Each generated skill shall inherit project-specific engineering standards from instructions.md. |

#### FR-4.8: Hooks generation

| ID | Requirement |
|---|---|
| FR-4.8.1 | System shall generate hook configurations: pre-commit validation, PR templates, lint rules, formatting rules, architecture validation, security checks, dependency validation. |
| FR-4.8.2 | Each hook generated by invoking "generate-hook-config" skill. |
| FR-4.8.3 | Hook rules shall enforce what instructions.md and org standards define. |

#### FR-4.9: Prompt library generation

| ID | Requirement |
|---|---|
| FR-4.9.1 | System shall generate project-specific prompts organized by category: service generation, API implementation, database access, event publishing, testing, refactoring, code review. |
| FR-4.9.2 | Each prompt tuned to the project's tech stack and instructions.md conventions. |

#### FR-4.10: Tool-specific configuration generation

| ID | Requirement |
|---|---|
| FR-4.10.1 | System shall generate AI assistant configs: .cursorrules, .github/copilot-instructions.md, Slingshot configuration. |
| FR-4.10.2 | Each generated using a tool-specific template filled with project context and org standards. |
| FR-4.10.3 | All tool configs shall produce equivalent guidance across different AI tools. |

#### FR-4.11: Artifact consistency

| ID | Requirement |
|---|---|
| FR-4.11.1 | All generated artifacts shall be internally consistent. |
| FR-4.11.2 | System shall perform a consistency check after generation and flag inconsistencies to the user. |

### FR-5: Project scaffolding

| ID | Requirement |
|---|---|
| FR-5.1 | System shall generate a project folder structure aligned with the architecture document's component design. If existing codebase was provided, scaffolding integrates with existing project. |
| FR-5.2 | System shall generate boilerplate configuration files (Docker, environment configs, CI/CD pipeline definitions). |
| FR-5.3 | System shall generate sample implementations of each identified architectural pattern with implementation, test file, and usage header. |
| FR-5.4 | System shall embed all AI artifacts in their correct scaffolding locations. |
| FR-5.5 | System shall generate a README with project overview, architecture summary, onboarding guide, and AI artifact pointers. |
| FR-5.6 | System shall output as a downloadable .zip archive named `{project_name}-scaffold-{timestamp}.zip`. |

### FR-6: Observability and audit

| ID | Requirement |
|---|---|
| FR-6.1 | All agent and skill executions shall be traced via LangSmith with inputs, outputs, token usage, latency, and prompt version. |
| FR-6.2 | System shall maintain a decision log capturing every decision, rationale, human overrides, and the org standard or best practice that informed each decision. |
| FR-6.3 | Review iteration count and history shall be persisted and visible. |
| FR-6.4 | Token usage and estimated cost shall be displayed per pipeline run and per agent. |
| FR-6.5 | Each skill invocation shall log the prompt template version used. When a prompt template is updated, the version increments automatically. Historical runs remain linked to the prompt version that produced them. |
| FR-6.6 | Partial pipeline failures shall be logged with the failed component, error details, retry attempts, and the state at time of failure. |

## 7. Non-functional requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | Full pipeline shall complete within 5 minutes for typical projects (3–4 docs, under 50 pages total). |
| NFR-2 | Performance | Individual reviewer agent shall complete within 60 seconds. |
| NFR-3 | Scalability | System shall handle documents up to 100 pages per file via map-reduce chunking. |
| NFR-4 | Reliability | Pipeline state persisted via SQLite checkpoint. Interrupted sessions resume from last completed stage. |
| NFR-5 | Reliability | Individual skill failures shall not crash the pipeline. Failed skills retry up to 2 times, then degrade gracefully (skip the failed component, inform the user, continue with remaining components). |
| NFR-6 | Reliability | All LLM outputs shall be validated against expected Pydantic schemas before being written to state. Malformed outputs trigger retry with an error-correction prompt. |
| NFR-7 | Usability | Frontend shall display pipeline progress with clear stage indicators. |
| NFR-8 | Usability | Review findings shall be browsable by domain and severity with expand/collapse views. |
| NFR-9 | Cost | Token usage tracked and displayed. Target: under 150K tokens per run (~$0.50) for typical projects. |
| NFR-10 | Extensibility | Adding a new reviewer domain requires only a new rubric YAML and agent config — no structural code changes. |
| NFR-11 | Portability | System runs locally without cloud dependencies. |
| NFR-12 | Data protection | Uploaded documents stored only in local session directory. Sessions isolated by unique ID. Documents deleted after session close or 24-hour inactivity. |
| NFR-13 | Data protection | No document content in application logs. Users informed that LangSmith traces contain LLM inputs/outputs. |
| NFR-14 | Data protection | API keys stored in environment variables, never in code or logs. |
| NFR-15 | Reusability | Sessions persisted in SQLite. Org standards reusable across sessions without re-uploading. |
| NFR-16 | Traceability | Every generated artifact is traceable to: the prompt version that produced it, the org standards that informed it, and the review findings that shaped it. |

## 8. Assumptions

- Users have existing BRD, architecture docs, and user stories before using the system.
- Input documents are in English and in markdown or text format (initial release).
- Users have access to an LLM API (Anthropic Claude or OpenAI GPT-4).
- Organization engineering standards are provided by the architect. Where missing, LLM best practices serve as fallback.
- The system is single-user per session.
- LLM-generated reviews are advisory — human judgment remains the final gate.

## 9. Constraints

- LLM context window limits require chunking for large documents. The system handles this via map-reduce within skills.
- Org standards must be concise enough to fit within the LLM context window alongside project context and agent prompt. Very large standards (>10K tokens) should be split into separate category files.
- Generated scaffolding is a starting point, not production-ready code.
- LangSmith traces contain document content sent to the LLM — users with confidential documents should use self-hosted LangSmith or disable tracing.

## 10. User journey

### Step 1 — Start a session
User opens the web UI, creates a new session with a project name.

### Step 2 — Upload documents
User uploads project documents (2–4 markdown/text files), tagged by type. Optionally provides existing codebase context.

### Step 3 — Upload org standards
User uploads org standards to the /standards section, or selects "reuse from previous session." System detects missing categories and displays warnings. System checks for conflicts between standards and surfaces them for resolution.

### Step 4 — Review extraction
System parses documents (chunking large ones as needed) and displays extracted ProjectContext. User verifies accuracy before proceeding.

### Step 5 — Pipeline runs review
Five reviewer cards transition from pending → running → complete with score badges. All run in parallel with real-time WebSocket updates.

### Step 6 — Review QA validation
After reviewers complete, the QA agent runs automatically. Findings are deduplicated, contradictions flagged, severity normalized, and a review quality score produced. This happens in seconds and is shown as a brief "Validating review quality..." stage.

### Step 7 — Review results
Dashboard shows: radar chart of domain scores, overall score, review quality score, QA-validated findings sorted by severity. Contradictions are highlighted with both reviewer positions. Deduplicated findings show contributing domains.

### Step 8 — Human decision
User reviews findings: accept, override (with justification), or revise. For contradictions, user must choose which recommendation to follow. If revising, only affected domains are re-reviewed.

### Step 9 — Generation
Pipeline generates AI artifacts and scaffolding using skills and prompt templates. UI shows generation progress including which org standards feed each artifact and which sections use defaults.

### Step 10 — Final approval and download
User reviews scaffolding in file tree preview, approves, downloads .zip. Session summary shows: scores, findings, overrides, generation decisions, org standard usage, prompt versions, and LangSmith trace link.

### Step 11 — Start coding
Developer extracts .zip, opens in IDE with Cursor/Copilot/Slingshot. AI assistant picks up instructions.md, skills, and conventions automatically.

## 11. Pipeline flow

```
Project docs + Org standards
       ↓
Document Parsing Agent (with chunking for large docs)
       ↓
ProjectContext (extraction preview → user confirms)
       ↓
Review Board (5 reviewers in parallel, each with routed org standards)
       ↓
Review Aggregator (deterministic: merge, score, sort)
       ↓
Review QA Agent (LLM: deduplicate, detect contradictions, validate quality)
       ↓
Human Approval Gate ←── revise & re-upload loop
       ↓
Context Synthesis Agent
       ↓
AI Development Setup Agent (invokes skills per artifact section)
       ↓
Consistency Checker (deterministic)
       ↓
Project Scaffolding Agent (invokes skills per scaffold component)
       ↓
Human Approval Gate
       ↓
Download .zip
```

## 12. ProjectContext schema

### 12.1 Extracted fields

```
ProjectContext
├── project_name: string
├── project_description: string
├── source_documents: list[string]
├── org_standards_loaded: list[string]
│
├── tech_stack: list[TechStackItem]
│   └── TechStackItem
│       ├── category: string
│       ├── technology: string
│       ├── version: string | null
│       └── justification: string | null
│
├── components: list[Component]
│   └── Component
│       ├── name: string
│       ├── type: string
│       ├── description: string
│       ├── tech_stack: list[TechStackItem]
│       ├── responsibilities: list[string]
│       ├── dependencies: list[string]
│       ├── api_contracts: list[string]
│       └── data_entities: list[string]
│
├── nfrs: list[NFR]
│   └── NFR
│       ├── category: string
│       ├── requirement: string
│       ├── source: string
│       ├── measurable: boolean
│       └── notes: string | null
│
├── stories: list[Story]
│   └── Story
│       ├── id: string
│       ├── title: string
│       ├── description: string
│       ├── acceptance_criteria: list[string]
│       ├── related_components: list[string]
│       └── estimated_complexity: string
│
├── gaps: list[Gap]
│   └── Gap
│       ├── description: string
│       ├── source_document: string
│       ├── severity: "critical" | "major" | "informational"
│       └── suggestion: string | null
│
├── existing_codebase: ExistingCodebase | null
│   └── ExistingCodebase
│       ├── source: string
│       ├── folder_structure: dict | null
│       ├── detected_stack: list[TechStackItem]
│       └── notes: string
│
├── org_standards: OrgStandards
│   └── OrgStandards
│       ├── coding: string | null
│       ├── security: string | null
│       ├── api_design: string | null
│       ├── naming: string | null
│       ├── logging: string | null
│       ├── exception_handling: string | null
│       ├── testing: string | null
│       ├── cicd: string | null
│       ├── repository_conventions: string | null
│       ├── organization_practices: string | null
│       ├── missing_categories: list[string]
│       └── conflicts: list[StandardConflict]
│           └── StandardConflict
│               ├── category_a: string
│               ├── statement_a: string
│               ├── category_b: string
│               ├── statement_b: string
│               ├── description: string
│               └── resolution: string | null
```

### 12.2 Review fields

```
├── reviews: list[ReviewResult]
│   └── ReviewResult
│       ├── domain: "architecture" | "security" | "performance" | "reliability" | "compliance"
│       ├── score: integer (1–10)
│       ├── dimension_scores: list[DimensionScore]
│       │   └── DimensionScore
│       │       ├── dimension: string
│       │       ├── score: integer (1–10)
│       │       └── justification: string
│       ├── findings: list[Finding]
│       │   └── Finding
│       │       ├── id: string
│       │       ├── severity: "critical" | "major" | "minor" | "suggestion"
│       │       ├── title: string
│       │       ├── description: string
│       │       ├── affected_components: list[string]
│       │       ├── recommendation: string
│       │       ├── based_on: string
│       │       ├── status: "open" | "accepted" | "overridden" | "resolved"
│       │       ├── override_justification: string | null
│       │       ├── duplicate_of: string | null       # set by QA agent if merged
│       │       └── contributing_domains: list[string] # set by QA agent for merged findings
│       ├── summary: string
│       └── reviewed_at: string
│
├── review_qa: ReviewQAResult | null
│   └── ReviewQAResult
│       ├── quality_score: integer (1-10)
│       ├── duplicates_found: integer
│       ├── contradictions: list[Contradiction]
│       │   └── Contradiction
│       │       ├── finding_id_a: string
│       │       ├── finding_id_b: string
│       │       ├── domain_a: string
│       │       ├── domain_b: string
│       │       ├── description: string
│       │       └── resolution: string | null    # set by human
│       ├── severity_normalizations: list[dict]
│       ├── low_quality_findings: list[string]   # finding IDs flagged
│       ├── coverage_warnings: list[string]      # domains with suspicious zero findings
│       └── summary: string
│
├── overall_score: float | null
├── remediation_summary: string | null
```

### 12.3 Generation fields

```
├── patterns: list[PatternDefinition]
│   └── PatternDefinition
│       ├── name: string
│       ├── description: string
│       ├── applicable_components: list[string]
│       ├── template_path: string
│       └── ai_skill_ref: string | null
│
├── ai_artifacts: list[AIArtifact]
│   └── AIArtifact
│       ├── type: string
│       ├── filename: string
│       ├── content: string
│       ├── derived_from: list[string]
│       ├── used_default: boolean
│       └── prompt_version: string
│
├── scaffolding_structure: dict | null
```

### 12.4 Pipeline state fields

```
├── current_stage: string
├── review_iteration: integer
├── failed_components: list[FailedComponent]
│   └── FailedComponent
│       ├── component: string
│       ├── error: string
│       ├── retry_count: integer
│       └── timestamp: string
│
├── human_decisions: list[HumanDecision]
│   └── HumanDecision
│       ├── timestamp: string
│       ├── action: "accept" | "override" | "revise" | "resolve_contradiction"
│       ├── finding_ids: list[string]
│       ├── justification: string | null
│       └── domain: string | null
│
└── decision_log: list[DecisionEntry]
    └── DecisionEntry
        ├── timestamp: string
        ├── agent: string
        ├── skill: string | null
        ├── prompt_version: string | null
        ├── decision: string
        ├── rationale: string
        ├── alternatives_considered: list[string]
        ├── context_refs: list[string]
        └── standard_refs: list[string]
```

## 13. Review rubrics

### 13.1 Scoring anchors (universal)

| Score range | Anchor definition |
|---|---|
| 1–2 | Not addressed. No meaningful coverage. |
| 3–4 | Mentioned but inadequate. Critical gaps remain. |
| 5–6 | Partially addressed. Lacks depth, specificity, or consistency. |
| 7–8 | Well addressed. Solid coverage with minor gaps. |
| 9–10 | Excellent. Comprehensive, specific, production-ready. |

### 13.2 Architecture review rubric

| Dimension | What it evaluates |
|---|---|
| Completeness | All components defined, interactions documented, data flows traceable |
| Pattern consistency | Coherent architectural style, deviations justified |
| Separation of concerns | Single-responsibility per component, clear bounded contexts |
| Data architecture | Data ownership, consistency model, migration strategy |
| API design | Contract clarity, versioning, error taxonomy, pagination |
| Scalability design | Horizontal scaling per component, statelessness, bottleneck identification |

### 13.3 Security review rubric

| Dimension | What it evaluates |
|---|---|
| Authentication & authorization | Auth mechanism, RBAC/ABAC, token lifecycle, session management |
| Data protection | Encryption at rest/transit, PII handling, data classification |
| API security | Rate limiting, input validation, CORS, injection prevention |
| Infrastructure security | Network segmentation, secrets management, least-privilege IAM |
| Dependency security | Supply chain awareness, vulnerability scanning, dependency pinning |
| Audit & logging | Security event logging, tamper-proof audit trail, monitoring |

### 13.4 Performance review rubric

| Dimension | What it evaluates |
|---|---|
| Latency design | Response time targets, async vs sync decisions, critical path |
| Caching strategy | Cache layers, invalidation strategy, cache pattern choice |
| Database performance | Indexing, query optimization, connection pooling, read replicas |
| Concurrency | Thread/worker pool sizing, backpressure, resource contention |
| Resource efficiency | Right-sizing, auto-scaling triggers, cold start mitigation |

### 13.5 Reliability review rubric

| Dimension | What it evaluates |
|---|---|
| Failure modes | Failure scenarios per component, blast radius, single points of failure |
| Resilience patterns | Circuit breakers, retries with backoff, bulkheads, timeout budgets |
| Data durability | Backup strategy, replication, RPO/RTO |
| Observability | Health checks, distributed tracing, structured logging, alerting |
| Graceful degradation | Fallback behaviors, feature flags, partial availability |

### 13.6 Compliance review rubric

| Dimension | What it evaluates |
|---|---|
| Data residency | Storage locations vs regulatory requirements |
| Privacy | GDPR/CCPA readiness, consent management, right to deletion |
| Regulatory | Industry-specific requirements (HIPAA, PCI-DSS, SOX) |
| Data retention | Retention policies, automated purge mechanisms |
| Auditability | Change tracking, access logs, compliance reporting |

### 13.7 Score weights

| Domain | Weight |
|---|---|
| Architecture | 25% |
| Security | 25% |
| Performance | 20% |
| Reliability | 20% |
| Compliance | 10% |

### 13.8 Org standard influence on review

When an org standard is provided, the reviewer evaluates compliance with that specific standard in addition to general best practices. Without an org standard, the reviewer uses LLM knowledge only.

## 14. Org standards management

### 14.1 Upload structure

```
/standards/
├── coding-standards.md
├── security-standards.md
├── api-design.md
├── naming-conventions.md
├── logging-standards.md
├── exception-handling.md
├── testing-standards.md
├── cicd-standards.md
├── repository-conventions.md
└── organization-practices.md
```

### 14.2 Routing to agents

| Standard category | Routed to reviewer | Routed to AI setup for |
|---|---|---|
| coding-standards | Architecture | instructions.md, skills, hooks (lint) |
| security-standards | Security | instructions.md, hooks (security checks) |
| api-design | Architecture, Performance | instructions.md, skills (API patterns), prompts |
| naming-conventions | Architecture | instructions.md, hooks (naming checks) |
| logging-standards | Reliability | instructions.md, skills, hooks |
| exception-handling | Reliability | instructions.md, skills |
| testing-standards | All reviewers | instructions.md, skills (test patterns) |
| cicd-standards | Compliance | hooks (CI/CD config), scaffolding |
| repository-conventions | Architecture | hooks (PR templates), scaffolding |
| organization-practices | All reviewers | instructions.md |

### 14.3 Conflict detection

Before the pipeline starts, the system scans all uploaded standards for conflicts. A conflict occurs when two standards prescribe contradictory rules (e.g., coding standard says "camelCase for all identifiers" but API design says "snake_case for request/response fields"). Conflicts are surfaced with both statements and source files. User must resolve or acknowledge before proceeding.

### 14.4 Missing standard handling

When a category is missing: warning displayed, reviewers use LLM best practices for that area, generated artifacts mark sections with default warning, `AIArtifact.used_default` set to true.

### 14.5 Session reuse

Org standards stored in SQLite. New sessions can load standards from previous sessions. User can add, replace, or remove individual standards after reuse.

## 15. MVP vs phase 2

### 15.1 MVP (week 1 target)

| Feature | Details |
|---|---|
| Document upload | Markdown/text files. Tagged upload. |
| Org standards upload | /standards with filename tagging. Missing category warnings. Conflict detection. |
| Document parsing | LLM extraction with map-reduce chunking for large docs. Extraction preview. Gap identification. |
| Review board | 5 reviewers in parallel with rubrics and org standard routing. Error handling with retry. |
| Review QA agent | Semantic deduplication, contradiction detection, severity normalization, actionability validation, coverage check, quality score. |
| Human approval gate | Accept / override per finding / revise & re-upload. Contradiction resolution. Decision logging. |
| AI dev setup | Skills/prompts/instructions layered design. Org-standard-aware generation. Default warnings. Prompt versioning. |
| Project scaffolding | Folder structure, boilerplate, pattern samples. Downloadable .zip. |
| Consistency checker | Validates artifact internal consistency. |
| Session persistence | SQLite. Org standards reuse across sessions. |
| Error handling | Retry logic, graceful degradation, output validation. |
| Observability | LangSmith tracing with prompt versions. Token usage tracking. |
| Frontend | All views: upload, extraction preview, pipeline, review dashboard, approval, generation progress, scaffolding preview, decision log, standards coverage. |

### 15.2 Phase 2

| Feature | Details |
|---|---|
| PDF/DOCX support | Document loaders for non-markdown formats. |
| Existing codebase analysis | Git repo cloning, structure analysis, stack detection. |
| Git repository bootstrap | Auto-init with branch strategy, PR templates, initial commit. |
| Stories enhancement | Enrich stories with scaffolding context and task breakdowns. |
| Local LLM support | Ollama integration for offline operation. |
| Export formats | PDF review report, Confluence-compatible markdown. |
| Review comparison | Side-by-side diff across review iterations. |
| Review history and learning | Track scores across projects, identify recurring weaknesses. |
| Override pattern learning | Identify consistently-overridden findings, suggest deprioritizing. |
| Artifact evolution | Use prior project artifacts as baseline for same-stack new projects. |
| Organization insights dashboard | Aggregate view across projects: common gaps, average scores, standard coverage. |

## 16. Success criteria

| Criterion | Measurable threshold |
|---|---|
| Pipeline completion | End-to-end in under 5 minutes for demo scenario with no manual intervention beyond approval gates. |
| Review specificity | ≥80% of findings reference a specific component (affected_components non-empty). |
| Review standard alignment | ≥70% of findings in standard-covered domains reference the org standard in based_on. |
| Review QA effectiveness | Review quality score ≥7 for well-structured architectures. Deduplication catches ≥90% of cross-domain duplicates. |
| Scoring consistency | Same input twice produces overall scores within ±1.0. |
| Contradiction detection | QA agent catches ≥80% of contradictions (validated against manually-identified contradictions in test data). |
| AI artifact usability | Generated instructions.md picked up by Cursor without modification. |
| Artifact consistency | Skills reference instructions.md conventions. Hook lint rules match coding standards. PR template traces to rubric. |
| Org standard reflection | When coding standard specifies camelCase, instructions.md + skills + hooks all enforce camelCase. Verified for ≥3 specific rules. |
| Default transparency | Missing org standard → corresponding artifact sections marked with default warning. |
| Scaffolding completeness | Generated .zip passes `npm install` and `lint` without errors. |
| Error resilience | Single reviewer failure doesn't crash pipeline. User informed, remaining reviewers complete. |
| Prompt traceability | Every generated artifact traceable to its prompt version in LangSmith. |
| Onboarding time | Unfamiliar developer locates correct pattern sample within 10 minutes. |
| Token budget | Under 150K tokens per run for typical projects. |
| Session reuse | New session reuses org standards from previous session without re-upload. |
