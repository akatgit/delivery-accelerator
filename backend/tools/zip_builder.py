"""Zip Builder (ARCHITECTURE_v2.0.md section 3.1; BRD_v2.0.md FR-5.6). A
deterministic tool -- no LLM. Turns a file manifest (path -> content) into a
downloadable .zip archive named ``{project_name}-scaffold-{timestamp}.zip``.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def build_zip_filename(project_name: str) -> str:
    """`{project_name}-scaffold-{timestamp}.zip` (FR-5.6)."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{_slugify(project_name)}-scaffold-{timestamp}.zip"


def build_zip_bytes(manifest: dict[str, str]) -> bytes:
    """Builds the .zip archive in memory from a file manifest and returns its
    raw bytes, e.g. for streaming directly as an HTTP response."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path, content in manifest.items():
            archive.writestr(file_path, content)
    return buffer.getvalue()


def build_zip(manifest: dict[str, str], project_name: str, output_dir: str | Path) -> Path:
    """Writes the .zip archive to `output_dir` and returns its path (FR-5.6)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / build_zip_filename(project_name)
    output_path.write_bytes(build_zip_bytes(manifest))
    return output_path
