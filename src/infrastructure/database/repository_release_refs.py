from __future__ import annotations

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


class ReleaseReferenceRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(
        self,
        *,
        manifest_id: UUID,
        render_job_id: UUID,
        package_hash: str,
        created_by: str,
        metadata: dict | None = None,
        quality_report_id: UUID | None = None,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.publication_packages (
                render_manifest_id,
                render_job_id,
                package_hash,
                metadata,
                created_by,
                quality_report_id
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                manifest_id,
                render_job_id,
                package_hash,
                Jsonb(metadata or {}),
                created_by,
                quality_report_id,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("Release reference was not created")
        return row
