from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(frozen=True, slots=True)
class PacketRecord:
    id: UUID
    workflow_run_id: UUID
    intake_id: UUID
    stage_execution_id: UUID | None
    packet_version: str
    status: str
    packet_hash: str
    source_metadata: list[dict[str, Any]]
    extracted_claims: list[dict[str, Any]]
    quote_boundaries: list[dict[str, Any]]
    entities: dict[str, Any]
    freshness: dict[str, Any]
    citations: list[dict[str, Any]]
    confidence_notes: str | None
    provider_metadata: dict[str, Any]
    created_by: str
    created_at: datetime


class PacketRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(self, *, workflow_run_id: UUID, intake_id: UUID, stage_execution_id: UUID | None, packet_hash: str, source_metadata: list[dict[str, Any]], extracted_claims: list[dict[str, Any]], quote_boundaries: list[dict[str, Any]], entities: dict[str, Any], freshness: dict[str, Any], citations: list[dict[str, Any]], confidence_notes: str | None, provider_metadata: dict[str, Any], created_by: str) -> PacketRecord:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.research_packets (
                workflow_run_id, intake_id, stage_execution_id, packet_hash,
                source_metadata, extracted_claims, quote_boundaries, entities,
                freshness, citations, confidence_notes, provider_metadata, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (workflow_run_id, intake_id, packet_hash) DO UPDATE
            SET provider_metadata = football_brief.research_packets.provider_metadata
            RETURNING *
            """,
            (
                workflow_run_id,
                intake_id,
                stage_execution_id,
                packet_hash,
                Jsonb(source_metadata),
                Jsonb(extracted_claims),
                Jsonb(quote_boundaries),
                Jsonb(entities),
                Jsonb(freshness),
                Jsonb(citations),
                confidence_notes,
                Jsonb(provider_metadata),
                created_by,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("packet was not persisted")
        return PacketRecord(**row)

    def get_by_hash(self, *, workflow_run_id: UUID, intake_id: UUID, packet_hash: str) -> PacketRecord | None:
        row = self.conn.execute(
            """
            SELECT * FROM football_brief.research_packets
            WHERE workflow_run_id = %s AND intake_id = %s AND packet_hash = %s
            """,
            (workflow_run_id, intake_id, packet_hash),
        ).fetchone()
        return PacketRecord(**row) if row else None

    def list_for_intake(self, intake_id: UUID) -> list[PacketRecord]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.research_packets WHERE intake_id = %s ORDER BY created_at DESC",
            (intake_id,),
        ).fetchall()
        return [PacketRecord(**row) for row in rows]
