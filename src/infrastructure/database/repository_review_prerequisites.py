from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection


@dataclass(frozen=True, slots=True)
class ReviewPrerequisiteRecord:
    id: UUID
    workflow_run_id: UUID
    packet_id: UUID
    intake_id: UUID
    status: str
    requested_by: str
    reviewed_by: str | None
    rationale: str | None
    created_at: datetime
    reviewed_at: datetime | None
    updated_at: datetime


class ReviewPrerequisiteRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create_pending(self, *, workflow_run_id: UUID, packet_id: UUID, intake_id: UUID, requested_by: str) -> ReviewPrerequisiteRecord:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.review_prerequisites (
                workflow_run_id, packet_id, intake_id, requested_by
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (workflow_run_id, packet_id) DO UPDATE
            SET status = football_brief.review_prerequisites.status
            RETURNING *
            """,
            (workflow_run_id, packet_id, intake_id, requested_by),
        ).fetchone()
        if row is None:
            raise RuntimeError("review prerequisite was not persisted")
        return ReviewPrerequisiteRecord(**row)

    def get_for_packet(self, *, workflow_run_id: UUID, packet_id: UUID) -> ReviewPrerequisiteRecord | None:
        row = self.conn.execute(
            """
            SELECT * FROM football_brief.review_prerequisites
            WHERE workflow_run_id = %s AND packet_id = %s
            """,
            (workflow_run_id, packet_id),
        ).fetchone()
        return ReviewPrerequisiteRecord(**row) if row else None

    def set_status(self, *, workflow_run_id: UUID, packet_id: UUID, status: str, reviewed_by: str, rationale: str | None) -> ReviewPrerequisiteRecord:
        row = self.conn.execute(
            """
            UPDATE football_brief.review_prerequisites
            SET status = %s,
                reviewed_by = %s,
                rationale = %s,
                reviewed_at = now()
            WHERE workflow_run_id = %s AND packet_id = %s
            RETURNING *
            """,
            (status, reviewed_by, rationale, workflow_run_id, packet_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("review prerequisite was not found")
        return ReviewPrerequisiteRecord(**row)

    def list_pending(self, workflow_run_id: UUID) -> list[ReviewPrerequisiteRecord]:
        rows = self.conn.execute(
            """
            SELECT * FROM football_brief.review_prerequisites
            WHERE workflow_run_id = %s AND status = 'pending'
            ORDER BY created_at DESC
            """,
            (workflow_run_id,),
        ).fetchall()
        return [ReviewPrerequisiteRecord(**row) for row in rows]
