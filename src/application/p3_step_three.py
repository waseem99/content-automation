from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from src.application.p3_step_two import P3StepTwoService
from src.application.workers.dispatcher import WorkerDispatcher
from src.application.workers.models import WorkerDefinition, WorkerExecutionRequest, WorkerExecutionResult, WorkerHandlerResult, WorkerOutcome
from src.application.workers.registry import WorkerRegistry
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class P3StepThreeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class P3PlanReview:
    id: UUID
    workflow_run_id: UUID
    step_plan_id: UUID
    status: str
    reviewed_by: str | None
    rationale: str | None
    created_at: datetime
    reviewed_at: datetime | None


@dataclass(frozen=True, slots=True)
class P3Package:
    id: UUID
    workflow_run_id: UUID
    step_plan_id: UUID
    stage_execution_id: UUID | None
    package_hash: str
    option_ids: list[str]
    scene_map: list[dict[str, Any]]
    lineage_refs: dict[str, Any]
    metadata: dict[str, Any]
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class P3PackageResult:
    worker_result: WorkerExecutionResult
    package: P3Package | None


class P3PlanReviewService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def request_review(self, *, workflow_run_id: UUID, step_plan_id: UUID, actor: str) -> P3PlanReview:
        with unit_of_work(self.database) as uow:
            _plan_for_workflow(uow.conn, workflow_run_id, step_plan_id)
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.p3_plan_reviews (workflow_run_id, step_plan_id)
                VALUES (%s, %s)
                ON CONFLICT (workflow_run_id, step_plan_id) DO UPDATE
                SET status = football_brief.p3_plan_reviews.status
                RETURNING *
                """,
                (workflow_run_id, step_plan_id),
            ).fetchone()
            review = P3PlanReview(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=None,
                event_type="p3_plan_review_requested",
                actor=actor,
                reason="package_prerequisite",
                payload={"step_plan_id": str(step_plan_id), "review_id": str(review.id)},
            )
            return review

    def decide(self, *, workflow_run_id: UUID, step_plan_id: UUID, status: str, reviewed_by: str, rationale: str | None = None) -> P3PlanReview:
        if status not in {"approved", "returned"}:
            raise P3StepThreeError("status must be approved or returned")
        with unit_of_work(self.database) as uow:
            _plan_for_workflow(uow.conn, workflow_run_id, step_plan_id)
            existing = uow.conn.execute(
                "SELECT * FROM football_brief.p3_plan_reviews WHERE workflow_run_id = %s AND step_plan_id = %s",
                (workflow_run_id, step_plan_id),
            ).fetchone()
            if existing is None:
                row = uow.conn.execute(
                    """
                    INSERT INTO football_brief.p3_plan_reviews (
                        workflow_run_id, step_plan_id, status, reviewed_by, rationale, reviewed_at
                    ) VALUES (%s, %s, %s, %s, %s, now())
                    RETURNING *
                    """,
                    (workflow_run_id, step_plan_id, status, reviewed_by, rationale),
                ).fetchone()
            else:
                row = uow.conn.execute(
                    """
                    UPDATE football_brief.p3_plan_reviews
                    SET status = %s, reviewed_by = %s, rationale = %s, reviewed_at = now()
                    WHERE workflow_run_id = %s AND step_plan_id = %s
                    RETURNING *
                    """,
                    (status, reviewed_by, rationale, workflow_run_id, step_plan_id),
                ).fetchone()
            review = P3PlanReview(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=None,
                event_type="p3_plan_review_decided",
                actor=reviewed_by,
                reason=status,
                payload={"step_plan_id": str(step_plan_id), "review_id": str(review.id), "status": status},
            )
            return review

    def require_approved(self, *, workflow_run_id: UUID, step_plan_id: UUID) -> dict[str, Any]:
        with unit_of_work(self.database) as uow:
            plan = _plan_for_workflow(uow.conn, workflow_run_id, step_plan_id)
            review = uow.conn.execute(
                "SELECT * FROM football_brief.p3_plan_reviews WHERE workflow_run_id = %s AND step_plan_id = %s",
                (workflow_run_id, step_plan_id),
            ).fetchone()
            if review is None:
                raise P3StepThreeError("step plan approval is missing")
            if review["status"] != "approved":
                raise P3StepThreeError("step plan is not approved")
            return dict(plan)


class P3PackageWorker:
    def __init__(self, database: Database) -> None:
        self.database = database

    def __call__(self, payload: dict[str, Any]) -> WorkerHandlerResult:
        workflow_id = UUID(payload["workflow_run_id"])
        step_plan_id = UUID(payload["step_plan_id"])
        option_ids = [UUID(value) for value in payload["option_ids"]]
        with unit_of_work(self.database) as uow:
            _plan_for_workflow(uow.conn, workflow_id, step_plan_id)
            options = _options_for_plan(uow.conn, workflow_id, step_plan_id, option_ids)
        scene_map = _scene_map(options)
        lineage = {
            "step_plan_id": str(step_plan_id),
            "option_ids": [str(option["id"]) for option in options],
            "requirement_ids": [str(option["requirement_id"]) for option in options],
        }
        return WorkerHandlerResult(
            output={
                "step_plan_id": str(step_plan_id),
                "option_ids": [str(option["id"]) for option in options],
                "scene_map": scene_map,
                "lineage_refs": lineage,
                "metadata": {"option_count": len(options), "scene_count": len(scene_map), "mode": "deterministic"},
            },
            units=Decimal("1"),
            unit_name="package",
            metadata={"mode": "deterministic"},
        )


def p3_package_definition() -> WorkerDefinition:
    return WorkerDefinition(
        name="p3_package_worker",
        version="1",
        input_schema_name="P3PackageInput",
        input_schema_version="1",
        output_schema_name="P3Package",
        output_schema_version="1",
        timeout_seconds=60,
        estimated_cost_usd=Decimal("0.0000"),
        idempotency_fields=("workflow_run_id", "step_plan_id", "option_ids"),
    )


class P3PackageService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.plan_reviews = P3PlanReviewService(database)
        self.option_reviews = P3StepTwoService(database)
        registry = WorkerRegistry()
        registry.register(p3_package_definition(), P3PackageWorker(database))
        self.dispatcher = WorkerDispatcher(database=database, registry=registry)

    def create_for_plan(self, *, workflow_run_id: UUID, step_plan_id: UUID, option_ids: list[UUID], actor: str) -> P3PackageResult:
        if not option_ids:
            raise P3StepThreeError("at least one approved option is required")
        self.plan_reviews.require_approved(workflow_run_id=workflow_run_id, step_plan_id=step_plan_id)
        approved_options = []
        for option_id in option_ids:
            option = self.option_reviews.require_approved(workflow_run_id=workflow_run_id, option_id=option_id)
            if option["step_plan_id"] != step_plan_id:
                raise P3StepThreeError("option does not belong to step plan")
            approved_options.append(option)
        canonical_option_ids = sorted(str(option["id"]) for option in approved_options)
        worker_result = self.dispatcher.execute(
            WorkerExecutionRequest(
                workflow_run_id=workflow_run_id,
                worker_name="p3_package_worker",
                worker_version="1",
                input_payload={
                    "workflow_run_id": str(workflow_run_id),
                    "step_plan_id": str(step_plan_id),
                    "option_ids": canonical_option_ids,
                },
                actor=actor,
                stage_name="p3_package_prep",
            )
        )
        if worker_result.outcome not in {WorkerOutcome.SUCCEEDED, WorkerOutcome.REUSED} or not worker_result.output or not worker_result.output_hash:
            return P3PackageResult(worker_result=worker_result, package=None)
        data = worker_result.output
        with unit_of_work(self.database) as uow:
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.p3_packages (
                    workflow_run_id, step_plan_id, stage_execution_id, package_hash,
                    option_ids, scene_map, lineage_refs, metadata, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workflow_run_id, step_plan_id, package_hash) DO UPDATE
                SET metadata = football_brief.p3_packages.metadata
                RETURNING *
                """,
                (
                    workflow_run_id,
                    step_plan_id,
                    worker_result.stage_execution_id,
                    worker_result.output_hash,
                    Jsonb(data["option_ids"]),
                    Jsonb(data["scene_map"]),
                    Jsonb(data["lineage_refs"]),
                    Jsonb({"worker": worker_result.idempotency_key, "reused": worker_result.reused, **dict(data.get("metadata", {}))}),
                    actor,
                ),
            ).fetchone()
            package = P3Package(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=worker_result.stage_execution_id,
                event_type="p3_package_created",
                actor=actor,
                reason="requires_final_review",
                payload={"package_id": str(package.id), "step_plan_id": str(step_plan_id)},
            )
            return P3PackageResult(worker_result=worker_result, package=package)


def _plan_for_workflow(conn, workflow_run_id: UUID, step_plan_id: UUID):
    row = conn.execute(
        "SELECT * FROM football_brief.step_plans WHERE workflow_run_id = %s AND id = %s",
        (workflow_run_id, step_plan_id),
    ).fetchone()
    if row is None:
        raise P3StepThreeError("step plan was not found for workflow")
    return row


def _options_for_plan(conn, workflow_run_id: UUID, step_plan_id: UUID, option_ids: list[UUID]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT o.*, r.requirement_index, r.scene_number, r.item_type, r.purpose
        FROM football_brief.p3_options o
        JOIN football_brief.p3_requirements r ON r.id = o.requirement_id
        WHERE o.workflow_run_id = %s AND o.step_plan_id = %s AND o.id = ANY(%s)
        ORDER BY r.requirement_index, o.id
        """,
        (workflow_run_id, step_plan_id, option_ids),
    ).fetchall()
    if len(rows) != len(set(option_ids)):
        raise P3StepThreeError("one or more options were not found for step plan")
    return [dict(row) for row in rows]


def _scene_map(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": str(option["requirement_id"]),
            "requirement_index": option["requirement_index"],
            "scene_number": option["scene_number"],
            "requirement_type": option["item_type"],
            "purpose": option["purpose"],
            "approved_option_id": str(option["id"]),
            "reference_type": option["reference_type"],
            "reference_value": option["reference_value"],
        }
        for option in options
    ]
