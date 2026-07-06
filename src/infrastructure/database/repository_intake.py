from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(frozen=True, slots=True)
class IntakeRecord:
    id: UUID
    workflow_run_id: UUID
    topic: str | None
    angle: str | None
    status: str
    canonical_input_hash: str
    football_metadata: dict[str, Any]
    metadata: dict[str, Any]
    created_by: str
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class IntakeRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(self, *, workflow_run_id: UUID, topic: str | None, angle: str | None, canonical_input_hash: str, football_metadata: dict[str, Any], metadata: dict[str, Any], created_by: str) -> IntakeRecord:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.content_intakes (
                workflow_run_id, topic, angle, canonical_input_hash,
                football_metadata, metadata, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (workflow_run_id, topic, angle, canonical_input_hash, Jsonb(football_metadata), Jsonb(metadata), created_by),
        ).fetchone()
        if row is None:
            raise RuntimeError("intake was not persisted")
        return IntakeRecord(**row)
