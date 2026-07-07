"""SQLite-backed session registry (ARCHITECTURE_v2.0.md section 10, 14.5).

A session exists independently of the LangGraph checkpoint: it's created,
documents/standards are uploaded, and org-standard conflicts are detected and
resolved -- all *before* the pipeline graph ever runs (FR-1.5: conflicts must
be surfaced and resolved "before the pipeline starts"). Once `/start` is
called, `session_id` is reused as the graph's `thread_id`, and the LangGraph
checkpointer (a separate SQLite database, see `graph/pipeline.py`) becomes
the source of truth for everything the graph computes; this store only
tracks the session-level metadata needed before and around that point.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


@dataclass
class SessionRecord:
    id: str
    project_name: str
    project_description: str
    created_at: str
    current_stage: str
    standards_dir: str | None
    raw_documents: dict[str, str] = field(default_factory=dict)
    conflicts: list[dict] = field(default_factory=list)


_COLUMNS = (
    "id",
    "project_name",
    "project_description",
    "created_at",
    "current_stage",
    "standards_dir",
    "raw_documents",
    "conflicts",
)
_JSON_COLUMNS = {"raw_documents", "conflicts"}


class SessionStore:
    """Thread-safe SQLite-backed CRUD for session metadata."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    project_name TEXT NOT NULL,
                    project_description TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    current_stage TEXT NOT NULL DEFAULT 'created',
                    standards_dir TEXT,
                    raw_documents TEXT NOT NULL DEFAULT '{}',
                    conflicts TEXT NOT NULL DEFAULT '[]'
                )
                """
            )

    def create_session(self, project_name: str, project_description: str) -> SessionRecord:
        record = SessionRecord(
            id=str(uuid.uuid4()),
            project_name=project_name,
            project_description=project_description,
            created_at=datetime.now(timezone.utc).isoformat(),
            current_stage="created",
            standards_dir=None,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (id, project_name, project_description, created_at, "
                "current_stage, standards_dir, raw_documents, conflicts) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.project_name,
                    record.project_description,
                    record.created_at,
                    record.current_stage,
                    record.standards_dir,
                    json.dumps(record.raw_documents),
                    json.dumps(record.conflicts),
                ),
            )
        return record

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return self._row_to_record(row) if row is not None else None

    def list_sessions(self) -> list[SessionRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def update_session(self, session_id: str, **fields) -> None:
        if not fields:
            return
        unknown = set(fields) - set(_COLUMNS)
        if unknown:
            raise ValueError(f"Unknown session field(s): {sorted(unknown)}")
        values = {k: (json.dumps(v) if k in _JSON_COLUMNS else v) for k, v in fields.items()}
        columns = ", ".join(f"{key} = ?" for key in values)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE sessions SET {columns} WHERE id = ?", [*values.values(), session_id])

    def add_raw_document(self, session_id: str, doc_type: str, content: str) -> None:
        record = self.get_session(session_id)
        if record is None:
            raise KeyError(session_id)
        documents = dict(record.raw_documents)
        documents[doc_type] = content
        self.update_session(session_id, raw_documents=documents)

    def set_conflicts(self, session_id: str, conflicts: list[dict]) -> None:
        self.update_session(session_id, conflicts=conflicts)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            project_name=row["project_name"],
            project_description=row["project_description"],
            created_at=row["created_at"],
            current_stage=row["current_stage"],
            standards_dir=row["standards_dir"],
            raw_documents=json.loads(row["raw_documents"]),
            conflicts=json.loads(row["conflicts"]),
        )


_store: SessionStore | None = None


def _sessions_db_path(database_url: str) -> str:
    """Session metadata lives in its own SQLite file, separate from the
    LangGraph checkpoint database (`graph/pipeline.py`), so this table never
    collides with LangGraph's own internal checkpoint tables."""
    from backend.graph.pipeline import sqlite_path_from_database_url

    base = Path(sqlite_path_from_database_url(database_url))
    return str(base.with_name(base.stem + "_sessions" + base.suffix))


def get_session_store() -> SessionStore:
    """Lazily construct (and cache) the process-wide SessionStore."""
    global _store
    if _store is None:
        from backend.config import settings

        _store = SessionStore(_sessions_db_path(settings.database_url))
    return _store


def reset_session_store() -> None:
    """Test-only hook: forces the next `get_session_store()` call to build a
    fresh store (e.g. against a different `settings.database_url`)."""
    global _store
    _store = None
