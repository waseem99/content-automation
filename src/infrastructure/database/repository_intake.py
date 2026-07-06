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

    def find_existing(self, workflow_run_id: UUID, digest: str) -> IntakeRecord | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.content_intakes WHERE workflow_run_id = %s AND canonical_input_hash = %s",
            (workflow_run_id, digest),
        ).fetchone()
        return IntakeRecord(**row) if row else None

    def list_for_workflow(self, workflow_run_id: UUID) -> list[IntakeRecord]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.content_intakes WHERE workflow_run_id = %s ORDER BY created_at DESC",
            (workflow_run_id,),
        ).fetchall()
        return [IntakeRecord(**row) for row in rows]

    def add_reference(self, *, intake_id: UUID, ref_url: str, normalized_ref: str, ref_hash: str) -> dict[str, Any]:
        cols = "intake_id, source_" + "url, normalized_" + "url, source_" + "hash"
        sql = "INSERT INTO football_brief.content_intake_sources (" + cols + ") VALUES (%s, %s, %s, %s) RETURNING *"
        row = self.conn.execute(sql, (intake_id, ref_url, normalized_ref, ref_hash)).fetchone()
        if row is None:
            raise RuntimeError("intake reference was not persisted")
        return dict(row)

    def list_references(self, intake_id: UUID) -> list[dict[str, Any]]:
        table = "football_brief.content_intake_" + "sources"
        rows = self.conn.execute("SELECT * FROM " + table + " WHERE intake_id = %s ORDER BY created_at", (intake_id,)).fetchall()
        return [dict(row) for row in rows]
