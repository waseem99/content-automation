from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(frozen=True, slots=True)
class StageOutputRecord:
    id: UUID
    workflow_run_id: UUID
    packet_id: UUID
    intake_id: UUID
    stage_execution_id: UUID | None
    draft_version: str
    status: str
    draft_hash: str
    title: str
    hook: str
    outline: list[dict[str, Any]]
    narration: list[dict[str, Any]]
    citation_map: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_by: str
    created_at: datetime


class StageOutputRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(self, *, workflow_run_id: UUID, packet_id: UUID, intake_id: UUID, stage_execution_id: UUID | None, draft_hash: str, title: str, hook: str, outline: list[dict[str, Any]], narration: list[dict[str, Any]], citation_map: list[dict[str, Any]], metadata: dict[str, Any], created_by: str) -> StageOutputRecord:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.draft_outputs (
                workflow_run_id, packet_id, intake_id, stage_execution_id, draft_hash,
                title, hook, outline, narration, citation_map, metadata, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (workflow_run_id, packet_id, draft_hash) DO UPDATE
            SET metadata = football_brief.draft_outputs.metadata
            RETURNING *
            """,
            (
                workflow_run_id,
                packet_id,
                intake_id,
                stage_execution_id,
                draft_hash,
                title,
                hook,
                Jsonb(outline),
                Jsonb(narration),
                Jsonb(citation_map),
                Jsonb(metadata),
                created_by,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("stage output was not persisted")
        return StageOutputRecord(**row)

    def list_for_packet(self, packet_id: UUID) -> list[StageOutputRecord]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.draft_outputs WHERE packet_id = %s ORDER BY created_at DESC",
            (packet_id,),
        ).fetchall()
        return [StageOutputRecord(**row) for row in rows]
