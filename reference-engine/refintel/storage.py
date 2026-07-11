from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from .models import ProjectStatus, ReferenceProject


WORKSPACE_SUBDIRS = (
    "source",
    "media",
    "frames/interval",
    "frames/scenes",
    "frames/preferred",
    "transcript",
    "analysis",
    "reports/assets",
    "exports",
    "logs",
)


class WorkspaceStore:
    def __init__(self, root: Path | str = "workspace") -> None:
        self.root = Path(root).expanduser().resolve()
        self.references_root = self.root / "references"
        self.db_path = self.root / "library.sqlite3"
        self.root.mkdir(parents=True, exist_ok=True)
        self.references_root.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reference_items (
                    reference_id TEXT PRIMARY KEY,
                    canonical_key TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    rights_declaration TEXT NOT NULL,
                    status TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    source_sha256 TEXT,
                    duration_seconds REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_summary TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_reference_items_platform
                    ON reference_items(platform);
                CREATE INDEX IF NOT EXISTS idx_reference_items_status
                    ON reference_items(status);
                CREATE TABLE IF NOT EXISTS processing_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(reference_id) REFERENCES reference_items(reference_id)
                );
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR REPLACE INTO schema_meta(key, value)
                    VALUES ('schema_version', 'p66.sqlite.v1');
                """
            )

    def create_workspace(self, reference_id: str) -> Path:
        path = (self.references_root / reference_id).resolve()
        if self.references_root not in path.parents:
            raise ValueError("reference_id produced an unsafe workspace path")
        path.mkdir(parents=True, exist_ok=True)
        for subdir in WORKSPACE_SUBDIRS:
            (path / subdir).mkdir(parents=True, exist_ok=True)
        return path

    def project_path(self, reference_id: str) -> Path:
        return self.references_root / reference_id / "project.json"

    def save_project(self, project: ReferenceProject) -> None:
        project.updated_at = datetime.now(UTC)
        workspace = self.create_workspace(project.reference_id)
        project.workspace_path = str(workspace)
        self.project_path(project.reference_id).write_text(
            project.model_dump_json(indent=2), encoding="utf-8"
        )
        media_duration = project.media.duration_seconds if project.media else None
        error_summary = project.errors[-1] if project.errors else None
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO reference_items (
                    reference_id, canonical_key, title, platform,
                    rights_declaration, status, workspace_path, source_sha256,
                    duration_seconds, created_at, updated_at, error_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(reference_id) DO UPDATE SET
                    title = excluded.title,
                    platform = excluded.platform,
                    rights_declaration = excluded.rights_declaration,
                    status = excluded.status,
                    workspace_path = excluded.workspace_path,
                    source_sha256 = excluded.source_sha256,
                    duration_seconds = excluded.duration_seconds,
                    updated_at = excluded.updated_at,
                    error_summary = excluded.error_summary
                """,
                (
                    project.reference_id,
                    project.source.canonical_key,
                    project.source.title,
                    project.source.platform.value,
                    project.access.declaration.value,
                    project.status.value,
                    project.workspace_path,
                    project.source.source_sha256,
                    media_duration,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                    error_summary,
                ),
            )

    def load_project(self, reference_id: str) -> ReferenceProject:
        path = self.project_path(reference_id)
        if not path.exists():
            raise FileNotFoundError(f"Unknown reference: {reference_id}")
        return ReferenceProject.model_validate_json(path.read_text(encoding="utf-8"))

    def find_by_canonical_key(self, canonical_key: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT reference_id FROM reference_items WHERE canonical_key = ?",
                (canonical_key,),
            ).fetchone()
        return str(row["reference_id"]) if row else None

    def list_references(self) -> list[dict[str, object]]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT reference_id, title, platform, rights_declaration, status,
                       workspace_path, duration_seconds, created_at, updated_at,
                       error_summary
                FROM reference_items
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def record_event(
        self,
        reference_id: str,
        *,
        stage: str,
        status: str,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO processing_events(
                    reference_id, stage, status, message, created_at, details_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    reference_id,
                    stage,
                    status,
                    message,
                    datetime.now(UTC).isoformat(),
                    json.dumps(details or {}, ensure_ascii=False),
                ),
            )

    def set_status(self, reference_id: str, status: ProjectStatus) -> ReferenceProject:
        project = self.load_project(reference_id)
        project.status = status
        self.save_project(project)
        return project
