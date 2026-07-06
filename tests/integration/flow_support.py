from __future__ import annotations

from uuid import uuid4

from src.domain.workflow_models import StageExecutionCreate
from src.domain.workflow_status import StageStatus
from src.infrastructure.database.uow import unit_of_work


def make_stage(database, workflow_id, name="stage", *, status=StageStatus.PENDING, input_hash="1" * 64):
    with unit_of_work(database) as uow:
        return uow.stage_executions.create(
            StageExecutionCreate(
                workflow_run_id=workflow_id,
                stage_name=f"{name}-{uuid4()}",
                stage_version="1",
                idempotency_key=f"stage-{uuid4()}",
                input_hash=input_hash,
                status=status,
                operator="pytest",
            )
        )


def events_for(database, workflow_id):
    with unit_of_work(database) as uow:
        return uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s ORDER BY id",
            (workflow_id,),
        ).fetchall()
