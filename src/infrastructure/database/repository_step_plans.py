from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


@dataclass(frozen=True, slots=True)
class SourceOutputReviewRecord:
    id: UUID
    workflow_run_id: UUID
    source_output_id: UUID
    packet_id: UUID
    status: str
    reviewed_by: str | None
    rationale: str | None
    created_at: datetime
    reviewed_at: datetime | None


@dataclass(frozen=True, slots=True)
class StepPlanRecord:
    id: UUID
    workflow_run_id: UUID
    source_output_id: UUID
    packet_id: UUID
    intake_id: UUID
    stage_execution_id: UUID | None
    plan_hash: str
    scenes: list[dict[str, Any]]
    requirements: list[dict[str, Any]]
    notes: list[dict[str, Any]]
    metadata: dict[str, Any]
    created_by: str
    created_at: datetime


class SourceOutputReviewRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def request(self, *, workflow_run_id: UUID, source_output_id: UUID, packet_id: UUID) -> SourceOutputReviewRecord:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.source_output_reviews (workflow_run_id, source_output_id, packet_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (workflow_run_id, source_output_id) DO UPDATE
            SET status = football_brief.source_output_reviews.status
            RETURNING *
            """,
            (workflow_run_id, source_output_id, packet_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("source output review was not persisted")
        return SourceOutputReviewRecord(**row)

    def approve(self, *, workflow_run_id: UUID, source_output_id: UUID, reviewed_by: str, rationale: str | None = None) -> SourceOutputReviewRecord:
        row = self.conn.execute(
            """
            UPDATE football_brief.source_output_reviews
            SET status = 'approved', reviewed_by = %s, rationale = %s, reviewed_at = now()
            WHERE workflow_run_id = %s AND source_output_id = %s
            RETURNING *
            """,
            (reviewed_by, rationale, workflow_run_id, source_output_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("source output review was not found")
        return SourceOutputReviewRecord(**row)

    def get(self, *, workflow_run_id: UUID, source_output_id: UUID) -> SourceOutputReviewRecord | None:
        row = self.conn.execute(
            "SELECT * FROM football_brief.source_output_reviews WHERE workflow_run_id = %s AND source_output_id = %s",
            (workflow_run_id, source_output_id),
        ).fetchone()
        return SourceOutputReviewRecord(**row) if row else None


class StepPlanRepository:
    def __init__(self, conn: Connection[dict]) -> None:
        self.conn = conn

    def create(self, *, workflow_run_id: UUID, source_output_id: UUID, packet_id: UUID, intake_id: UUID, stage_execution_id: UUID | None, plan_hash: str, scenes: list[dict[str, Any]], requirements: list[dict[str, Any]], notes: list[dict[str, Any]], metadata: dict[str, Any], created_by: str) -> StepPlanRecord:
        row = self.conn.execute(
            """
            INSERT INTO football_brief.step_plans (
                workflow_run_id, source_output_id, packet_id, intake_id, stage_execution_id,
                plan_hash, scenes, requirements, notes, metadata, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (workflow_run_id, source_output_id, plan_hash) DO UPDATE
            SET metadata = football_brief.step_plans.metadata
            RETURNING *
            """,
            (
                workflow_run_id,
                source_output_id,
                packet_id,
                intake_id,
                stage_execution_id,
                plan_hash,
                Jsonb(scenes),
                Jsonb(requirements),
                Jsonb(notes),
                Jsonb(metadata),
                created_by,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("step plan was not persisted")
        return StepPlanRecord(**row)

    def list_for_source_output(self, source_output_id: UUID) -> list[StepPlanRecord]:
        rows = self.conn.execute(
            "SELECT * FROM football_brief.step_plans WHERE source_output_id = %s ORDER BY created_at DESC",
            (source_output_id,),
        ).fetchall()
        return [StepPlanRecord(**row) for row in rows]
