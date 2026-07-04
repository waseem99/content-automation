from __future__ import annotations

from uuid import UUID

from psycopg import Connection


class RenderJobRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(self, manifest_id: UUID) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.render_jobs (render_manifest_id)
            VALUES (%s)
            RETURNING *
            """,
            (manifest_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Render job was not created")
        return row

    def set_running(self, job_id: UUID) -> dict:
        row = self.conn.execute(
            """
            UPDATE football_brief.render_jobs
            SET status = 'running', started_at = now()
            WHERE id = %s AND status = 'pending'
            RETURNING *
            """,
            (job_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("Render job could not start")
        return row

    def set_succeeded(self, job_id: UUID, output_asset_id: UUID | None = None) -> dict:
        row = self.conn.execute(
            """
            UPDATE football_brief.render_jobs
            SET status = 'succeeded', output_asset_id = %s, completed_at = now()
            WHERE id = %s AND status = 'running'
            RETURNING *
            """,
            (output_asset_id, job_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("Render job could not complete")
        return row

    def set_failed(self, job_id: UUID, message: str) -> dict:
        row = self.conn.execute(
            """
            UPDATE football_brief.render_jobs
            SET status = 'failed', error_message = %s, completed_at = now()
            WHERE id = %s AND status IN ('pending', 'running')
            RETURNING *
            """,
            (message, job_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("Render job could not fail")
        return row

    def get(self, job_id: UUID) -> dict:
        row = self.conn.execute(
            "SELECT * FROM football_brief.render_jobs WHERE id = %s",
            (job_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Render job was not found: {job_id}")
        return row
