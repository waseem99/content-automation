from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.workers.dispatcher import WorkerDispatcher
from src.application.workers.models import WorkerDefinition, WorkerExecutionRequest, WorkerExecutionResult, WorkerHandlerResult, WorkerOutcome
from src.application.workers.registry import WorkerRegistry
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_stage_outputs import StageOutputRecord
from src.infrastructure.database.repository_step_plans import SourceOutputReviewRecord, SourceOutputReviewRepository, StepPlanRecord, StepPlanRepository
from src.infrastructure.database.uow import unit_of_work


class StepPlanError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StepPlanResult:
    worker_result: WorkerExecutionResult
    plan: StepPlanRecord | None


class StepPlanReviewService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def request(self, *, workflow_run_id: UUID, source_output_id: UUID) -> SourceOutputReviewRecord:
        with unit_of_work(self.database) as uow:
            output = _source_output(uow.conn, workflow_run_id, source_output_id)
            review = SourceOutputReviewRepository(uow.conn).request(
                workflow_run_id=workflow_run_id,
                source_output_id=source_output_id,
                packet_id=output.packet_id,
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=output.stage_execution_id,
                event_type="source_output_review_requested",
                actor="system",
                reason="planning_prerequisite",
                payload={"source_output_id": str(source_output_id), "review_id": str(review.id)},
            )
            return review

    def approve(self, *, workflow_run_id: UUID, source_output_id: UUID, reviewed_by: str, rationale: str | None = None) -> SourceOutputReviewRecord:
        with unit_of_work(self.database) as uow:
            output = _source_output(uow.conn, workflow_run_id, source_output_id)
            review = SourceOutputReviewRepository(uow.conn).approve(
                workflow_run_id=workflow_run_id,
                source_output_id=source_output_id,
                reviewed_by=reviewed_by,
                rationale=rationale,
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=output.stage_execution_id,
                event_type="source_output_review_approved",
                actor=reviewed_by,
                reason="approved_for_planning",
                payload={"source_output_id": str(source_output_id), "review_id": str(review.id)},
            )
            return review

    def require_approved(self, *, workflow_run_id: UUID, source_output_id: UUID) -> StageOutputRecord:
        with unit_of_work(self.database) as uow:
            output = _source_output(uow.conn, workflow_run_id, source_output_id)
            review = SourceOutputReviewRepository(uow.conn).get(workflow_run_id=workflow_run_id, source_output_id=source_output_id)
            if review is None:
                raise StepPlanError("source output review is missing")
            if review.status != "approved":
                raise StepPlanError("source output is not approved for planning")
            return output


def _source_output(conn, workflow_run_id: UUID, source_output_id: UUID) -> StageOutputRecord:
    row = conn.execute(
        "SELECT * FROM football_brief.draft_outputs WHERE id = %s AND workflow_run_id = %s",
        (source_output_id, workflow_run_id),
    ).fetchone()
    if row is None:
        raise StepPlanError("source output was not found for workflow")
    return StageOutputRecord(**row)


def _plan_payload(output: StageOutputRecord) -> dict[str, Any]:
    narration = output.narration or []
    rows = narration if narration else [{"order": 1, "line": output.hook, "citation_ids": []}]
    scenes = [
        {
            "scene_number": int(item.get("order", index)),
            "purpose": "support narration",
            "narration_line": item.get("line", output.hook),
            "citation_ids": list(item.get("citation_ids", [])),
            "visual_direction": "Create an original football visual treatment; do not attach third-party media here.",
        }
        for index, item in enumerate(rows, start=1)
    ]
    requirements = [
        {
            "scene_number": scene["scene_number"],
            "type": "original_visual_or_graphic",
            "purpose": scene["purpose"],
            "needs_rights_review": True,
            "approved_asset_id": None,
        }
        for scene in scenes
    ]
    notes = [
        {
            "scope": "planning_only",
            "note": "No third-party media is approved or attached by this step.",
        }
    ]
    return {
        "scenes": scenes,
        "requirements": requirements,
        "notes": notes,
        "metadata": {"source_output_hash": output.draft_hash, "scene_count": len(scenes)},
    }


class StepPlanWorker:
    def __init__(self, database: Database) -> None:
        self.database = database

    def __call__(self, payload: dict[str, Any]) -> WorkerHandlerResult:
        workflow_id = UUID(payload["workflow_run_id"])
        source_output_id = UUID(payload["source_output_id"])
        with unit_of_work(self.database) as uow:
            output = _source_output(uow.conn, workflow_id, source_output_id)
        return WorkerHandlerResult(
            output=_plan_payload(output),
            units=Decimal("1"),
            unit_name="plan",
            metadata={"mode": "deterministic", "source_output_id": str(source_output_id)},
        )


def step_plan_definition() -> WorkerDefinition:
    return WorkerDefinition(
        name="step_plan_worker",
        version="1",
        input_schema_name="StepPlanInput",
        input_schema_version="1",
        output_schema_name="StepPlan",
        output_schema_version="1",
        timeout_seconds=60,
        estimated_cost_usd=Decimal("0.0000"),
        idempotency_fields=("workflow_run_id", "source_output_id"),
    )


class StepPlanService:
    def __init__(self, database: Database) -> None:
        self.database = database
        registry = WorkerRegistry()
        registry.register(step_plan_definition(), StepPlanWorker(database))
        self.dispatcher = WorkerDispatcher(database=database, registry=registry)
        self.reviews = StepPlanReviewService(database)

    def create_for_output(self, *, workflow_run_id: UUID, source_output_id: UUID, actor: str) -> StepPlanResult:
        output = self.reviews.require_approved(workflow_run_id=workflow_run_id, source_output_id=source_output_id)
        worker_result = self.dispatcher.execute(
            WorkerExecutionRequest(
                workflow_run_id=workflow_run_id,
                worker_name="step_plan_worker",
                worker_version="1",
                input_payload={"workflow_run_id": str(workflow_run_id), "source_output_id": str(source_output_id)},
                actor=actor,
                stage_name="step_plan",
            )
        )
        if worker_result.outcome not in {WorkerOutcome.SUCCEEDED, WorkerOutcome.REUSED} or not worker_result.output or not worker_result.output_hash:
            return StepPlanResult(worker_result=worker_result, plan=None)

        data = worker_result.output
        with unit_of_work(self.database) as uow:
            plan = StepPlanRepository(uow.conn).create(
                workflow_run_id=workflow_run_id,
                source_output_id=source_output_id,
                packet_id=output.packet_id,
                intake_id=output.intake_id,
                stage_execution_id=worker_result.stage_execution_id,
                plan_hash=worker_result.output_hash,
                scenes=list(data.get("scenes", [])),
                requirements=list(data.get("requirements", [])),
                notes=list(data.get("notes", [])),
                metadata={"worker": worker_result.idempotency_key, "reused": worker_result.reused, **dict(data.get("metadata", {}))},
                created_by=actor,
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=worker_result.stage_execution_id,
                event_type="step_plan_created",
                actor=actor,
                reason="requires_human_review",
                payload={"plan_id": str(plan.id), "source_output_id": str(source_output_id)},
            )
        return StepPlanResult(worker_result=worker_result, plan=plan)
