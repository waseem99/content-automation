from __future__ import annotations

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


class WorkflowEventRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(
        self,
        *,
        workflow_run_id: UUID,
        stage_execution_id: UUID | None,
        event_type: str,
        actor: str,
        reason: str,
        payload: dict,
        from_status: str | None = None,
        to_status: str | None = None,
    ) -> dict:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.workflow_events (
                workflow_run_id,
                stage_execution_id,
                event_type,
                from_status,
                to_status,
                actor,
                reason,
                payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                workflow_run_id,
                stage_execution_id,
                event_type,
                from_status,
                to_status,
                actor,
                reason,
                Jsonb(payload),
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("Workflow event was not persisted")
        return row
