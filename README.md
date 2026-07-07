# ASDA — Agentic Solution Delivery Accelerator

ASDA reviews a project's architecture documents against your organization's
engineering standards using a multi-agent LangGraph pipeline, then generates
an AI-ready project scaffold (`instructions.md`, skill files, hooks, prompt
library, `.cursorrules`/Copilot/Slingshot configs, sample pattern
implementations) as a downloadable `.zip`.

Two human approval gates sit in the pipeline: one after the review board and
QA pass, one after scaffolding is generated — nothing gets enforced or
packaged without a human explicitly accepting it.

For the full requirements and design, see:
- [`docs/BRD_v2.0.md`](docs/BRD_v2.0.md) — functional requirements
- [`docs/ARCHITECTURE_v2.0.md`](docs/ARCHITECTURE_v2.0.md) — system design, pipeline flow, API contract

## Tech stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (state machine, parallel fan-out, human-in-the-loop interrupts, SQLite checkpointing) |
| Agent framework | LangChain |
| LLM | Anthropic Claude (`claude-sonnet-4-6` by default) |
| Observability | LangSmith (optional) |
| Backend API | FastAPI + Uvicorn (Python 3.11+) |
| Frontend | React 18, Tailwind CSS, Recharts, Vite |
| Persistence | SQLite (pipeline checkpoints + session metadata) |

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- An **Anthropic API key** — required for anything that invokes an LLM (parsing
  documents, running reviews, generating artifacts). Session/document/standards
  CRUD endpoints work without one.

## 1. Backend setup

From the repository root:

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install the backend and its dependencies
pip install -e .

# Configure environment variables
cp .env.example .env
```

Edit `.env` and set at least:

```
ANTHROPIC_API_KEY=sk-ant-...
```

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(empty)* | Required for any pipeline run |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Model used by every agent/skill |
| `LANGSMITH_API_KEY` | *(empty)* | Optional — enables tracing (FR-6.1) |
| `LANGSMITH_PROJECT` | `asda` | LangSmith project name |
| `DATABASE_URL` | `sqlite:///./pipeline_state.db` | LangGraph checkpoint DB (session metadata is stored alongside it, in a sibling `*_sessions.db` file) |
| `MAX_RETRIES` | `2` | Retries per skill invocation (transport + validation) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `6000` / `500` | Map-reduce chunking thresholds for large documents |
| `SCAFFOLD_OUTPUT_DIR` | `./scaffolds` | Where generated `.zip` archives are written |
| `UPLOADS_DIR` | `./uploads` | Where uploaded org standards files are stored |

## 2. Frontend setup

```bash
cd frontend
npm install
```

## 3. Run the app

You need both processes running at the same time, in two terminals.

**Terminal 1 — backend** (from the repository root, with the venv activated):

```bash
uvicorn backend.main:app --reload --port 8000
```

Verify it's up:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

Interactive API docs are at `http://localhost:8000/docs`.

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser. The dev server proxies
`/api/*` (including the WebSocket at `/api/sessions/{id}/stream`) through to
the backend on port 8000, so the browser only ever talks to one origin.

> If port 8000 is already in use, start the backend on another port (e.g.
> `--port 8010`) and point the frontend at it: `VITE_API_BASE_URL=http://localhost:8010 npm run dev`.

### Using the app

1. **Upload** — create a session, upload project documents (BRD, architecture
   doc, stories, tech preferences) and org standards files. Resolve any
   detected standard conflicts before starting.
2. Click **Start pipeline**. The stage indicator at the top tracks progress:
   Upload → Parse → Review → QA → Approve → Generate → Scaffold → Deliver.
3. When the pipeline pauses at the **first approval gate**, review the
   dashboard (domain radar chart, findings, contradictions) and either accept,
   override specific findings, resolve contradictions, or send it back for
   revision.
4. The pipeline generates `instructions.md`, skill files, hooks, prompts, and
   tool configs, then scaffolds the project.
5. At the **second approval gate**, preview the file tree and approve to
   build the final `.zip`, or reject to regenerate.
6. Download the archive from the **Scaffolding** tab.

## Running tests

```bash
python -m pytest
```

## Building the frontend for production

```bash
cd frontend
npm run build    # outputs to frontend/dist/
npm run preview  # serve the production build locally to sanity-check it
```

## Project structure

```
backend/
├── main.py                  # FastAPI app, router registration
├── config.py                # Environment-driven settings
├── api/                     # Routes, request/response models, session store, WS manager
├── agents/                  # Thin orchestrators (document parser, reviewers, QA, synthesis, setup, scaffolder)
├── skills/                  # Reusable LLM tasks, grouped by pipeline phase
├── prompts/                 # Versioned prompt templates + base instructions
├── graph/                   # LangGraph state, nodes, and pipeline wiring
├── schemas/                 # Pydantic models (ProjectContext, review, artifacts, pipeline)
├── rubrics/                 # Review scoring rubrics (YAML)
├── templates/               # Jinja2 scaffolding/tool-config templates
└── tools/                   # Deterministic logic (aggregation, consistency checks, zip building, standards loading)

frontend/
└── src/
    ├── api/client.js         # Backend API client
    ├── context/               # Global state (React context + useReducer)
    ├── hooks/useWebSocket.js  # Real-time pipeline updates
    └── components/            # The 9 views (Upload, Extraction, Pipeline, Review, Approval, Generation, Scaffolding, Decision Log, Standards)

tests/                     # pytest suite, mirrors backend/ structure
docs/                      # BRD, architecture, and implementation guide
```

## Troubleshooting

- **`Event loop is closed` / WebSocket updates never arrive** — make sure
  you're hitting the backend through `uvicorn` (which keeps one persistent
  event loop for the app's lifetime), not a one-off script.
- **Pipeline stuck / nothing happens after "Start pipeline"** — check the
  backend terminal for LLM errors; a missing or invalid `ANTHROPIC_API_KEY`
  will cause every skill call to fail (they retry, then get logged to
  "failed components" and gracefully skipped rather than crashing the run).
- **`sqlite3.OperationalError: database is locked`** — avoid running multiple
  backend processes against the same `DATABASE_URL` simultaneously.
