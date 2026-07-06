from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class P3StepOneError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class P3StepResult:
    id: UUID
    created: bool


def _hash_payload(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


class P3StepOneService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def materialize_requirements(self, *, workflow_run_id: UUID, step_plan_id: UUID, actor: str) -> list[dict[str, Any]]:
        with unit_of_work(self.database) as uow:
            plan = uow.conn.execute(
                "SELECT * FROM football_brief.step_plans WHERE workflow_run_id = %s AND id = %s",
                (workflow_run_id, step_plan_id),
            ).fetchone()
            if plan is None:
                raise P3StepOneError("step plan was not found for workflow")
            rows = []
            for index, item in enumerate(plan["requirements"], start=1):
                row = uow.conn.execute(
                    """
                    INSERT INTO football_brief.p3_requirements (
                        workflow_run_id, step_plan_id, requirement_index, scene_number,
                        item_type, purpose, metadata, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (step_plan_id, requirement_index) DO UPDATE
                    SET metadata = football_brief.p3_requirements.metadata
                    RETURNING *
                    """,
                    (
                        workflow_run_id,
                        step_plan_id,
                        index,
                        item.get("scene_number"),
                        str(item.get("type", "original_visual_or_graphic")),
                        item.get("purpose"),
                        Jsonb(dict(item)),
                        actor,
                    ),
                ).fetchone()
                rows.append(dict(row))
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=plan["stage_execution_id"],
                event_type="p3_requirements_materialized",
                actor=actor,
                reason="step_plan_requirements",
                payload={"step_plan_id": str(step_plan_id), "requirement_count": len(rows)},
            )
            return rows

    def list_requirements(self, step_plan_id: UUID) -> list[dict[str, Any]]:
        with unit_of_work(self.database) as uow:
            return [
                dict(row)
                for row in uow.conn.execute(
                    "SELECT * FROM football_brief.p3_requirements WHERE step_plan_id = %s ORDER BY requirement_index",
                    (step_plan_id,),
                ).fetchall()
            ]

    def add_option(self, *, workflow_run_id: UUID, requirement_id: UUID, reference_type: str, reference_value: str, reference_metadata: dict[str, Any] | None = None, notes: str | None = None, actor: str) -> dict[str, Any]:
        if not reference_type.strip() or not reference_value.strip():
            raise P3StepOneError("reference type and value are required")
        metadata = dict(reference_metadata or {})
        digest = _hash_payload({"type": reference_type.strip().lower(), "value": reference_value.strip(), "metadata": metadata})
        with unit_of_work(self.database) as uow:
            requirement = uow.conn.execute(
                "SELECT * FROM football_brief.p3_requirements WHERE workflow_run_id = %s AND id = %s",
                (workflow_run_id, requirement_id),
            ).fetchone()
            if requirement is None:
                raise P3StepOneError("requirement was not found for workflow")
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.p3_options (
                    workflow_run_id, requirement_id, step_plan_id, option_hash,
                    reference_type, reference_value, reference_metadata, notes, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (requirement_id, option_hash) DO UPDATE
                SET reference_metadata = football_brief.p3_options.reference_metadata
                RETURNING *
                """,
                (
                    workflow_run_id,
                    requirement_id,
                    requirement["step_plan_id"],
                    digest,
                    reference_type.strip().lower(),
                    reference_value.strip(),
                    Jsonb(metadata),
                    notes,
                    actor,
                ),
            ).fetchone()
            uow.conn.execute("UPDATE football_brief.p3_requirements SET status = 'option_added' WHERE id = %s", (requirement_id,))
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=None,
                event_type="p3_option_added",
                actor=actor,
                reason="operator_selection",
                payload={"requirement_id": str(requirement_id), "option_id": str(row["id"])},
            )
            return dict(row)

    def list_options(self, requirement_id: UUID) -> list[dict[str, Any]]:
        with unit_of_work(self.database) as uow:
            return [
                dict(row)
                for row in uow.conn.execute(
                    "SELECT * FROM football_brief.p3_options WHERE requirement_id = %s ORDER BY created_at DESC",
                    (requirement_id,),
                ).fetchall()
            ]
