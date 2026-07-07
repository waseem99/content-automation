from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from src.application.p3_step_four import P3PackageReviewService
from src.application.workers.dispatcher import WorkerDispatcher
from src.application.workers.models import WorkerDefinition, WorkerExecutionRequest, WorkerExecutionResult, WorkerHandlerResult, WorkerOutcome
from src.application.workers.registry import WorkerRegistry
from src.infrastructure.database.connection import Database
from src.infrastructure.database.uow import unit_of_work


class P3StepFiveError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class P3DeliveryManifest:
    id: UUID
    workflow_run_id: UUID
    package_id: UUID
    step_plan_id: UUID
    stage_execution_id: UUID | None
    manifest_hash: str
    manifest: dict[str, Any]
    lineage_refs: dict[str, Any]
    approval_metadata: dict[str, Any]
    package_metadata: dict[str, Any]
    created_by: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class P3DeliveryManifestResult:
    worker_result: WorkerExecutionResult
    manifest: P3DeliveryManifest | None


class P3DeliveryManifestWorker:
    def __init__(self, database: Database) -> None:
        self.database = database

    def __call__(self, payload: dict[str, Any]) -> WorkerHandlerResult:
        workflow_id = UUID(payload["workflow_run_id"])
        package_id = UUID(payload["package_id"])
        with unit_of_work(self.database) as uow:
            package = _package_for_workflow(uow.conn, workflow_id, package_id)
            review = _approved_review_for_package(uow.conn, workflow_id, package_id)
        option_ids = [str(value) for value in package["option_ids"]]
        manifest = {
            "workflow_run_id": str(workflow_id),
            "package_id": str(package_id),
            "step_plan_id": str(package["step_plan_id"]),
            "package_hash": package["package_hash"],
            "selected_option_ids": option_ids,
            "selected_asset_ids": option_ids,
            "stage_execution_id": str(package["stage_execution_id"]) if package["stage_execution_id"] else None,
            "scene_map": package["scene_map"],
            "approval_status": review["status"],
        }
        approval_metadata = {
            "review_id": str(review["id"]),
            "status": review["status"],
            "reviewed_by": review["reviewed_by"],
            "rationale": review["rationale"],
            "decision_metadata": review["decision_metadata"],
            "reviewed_at": review["reviewed_at"].isoformat() if review["reviewed_at"] else None,
        }
        lineage_refs = {
            "package_id": str(package_id),
            "step_plan_id": str(package["step_plan_id"]),
            "stage_execution_id": str(package["stage_execution_id"]) if package["stage_execution_id"] else None,
            "package_lineage_refs": package["lineage_refs"],
            "option_ids": option_ids,
        }
        return WorkerHandlerResult(
            output={
                "manifest": manifest,
                "lineage_refs": lineage_refs,
                "approval_metadata": approval_metadata,
                "package_metadata": package["metadata"],
            },
            units=Decimal("1"),
            unit_name="delivery_manifest",
            metadata={"mode": "deterministic"},
        )


def p3_delivery_manifest_definition() -> WorkerDefinition:
    return WorkerDefinition(
        name="p3_delivery_manifest_worker",
        version="1",
        input_schema_name="P3DeliveryManifestInput",
        input_schema_version="1",
        output_schema_name="P3DeliveryManifest",
        output_schema_version="1",
        timeout_seconds=60,
        estimated_cost_usd=Decimal("0.0000"),
        idempotency_fields=("workflow_run_id", "package_id"),
    )


class P3DeliveryManifestService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.package_reviews = P3PackageReviewService(database)
        registry = WorkerRegistry()
        registry.register(p3_delivery_manifest_definition(), P3DeliveryManifestWorker(database))
        self.dispatcher = WorkerDispatcher(database=database, registry=registry)

    def create_for_package(self, *, workflow_run_id: UUID, package_id: UUID, actor: str) -> P3DeliveryManifestResult:
        package = self.package_reviews.require_approved(workflow_run_id=workflow_run_id, package_id=package_id)
        worker_result = self.dispatcher.execute(
            WorkerExecutionRequest(
                workflow_run_id=workflow_run_id,
                worker_name="p3_delivery_manifest_worker",
                worker_version="1",
                input_payload={"workflow_run_id": str(workflow_run_id), "package_id": str(package_id)},
                actor=actor,
                stage_name="p3_delivery_manifest",
            )
        )
        if worker_result.outcome not in {WorkerOutcome.SUCCEEDED, WorkerOutcome.REUSED} or not worker_result.output or not worker_result.output_hash:
            return P3DeliveryManifestResult(worker_result=worker_result, manifest=None)
        data = worker_result.output
        with unit_of_work(self.database) as uow:
            row = uow.conn.execute(
                """
                INSERT INTO football_brief.p3_delivery_manifests (
                    workflow_run_id, package_id, step_plan_id, stage_execution_id,
                    manifest_hash, manifest, lineage_refs, approval_metadata,
                    package_metadata, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (workflow_run_id, package_id, manifest_hash) DO UPDATE
                SET package_metadata = football_brief.p3_delivery_manifests.package_metadata
                RETURNING *
                """,
                (
                    workflow_run_id,
                    package_id,
                    package["step_plan_id"],
                    worker_result.stage_execution_id,
                    worker_result.output_hash,
                    Jsonb(data["manifest"]),
                    Jsonb(data["lineage_refs"]),
                    Jsonb(data["approval_metadata"]),
                    Jsonb(data["package_metadata"]),
                    actor,
                ),
            ).fetchone()
            manifest = P3DeliveryManifest(**row)
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=worker_result.stage_execution_id,
                event_type="p3_delivery_manifest_created",
                actor=actor,
                reason="delivery_manifest_ready",
                payload={"manifest_id": str(manifest.id), "package_id": str(package_id)},
            )
            return P3DeliveryManifestResult(worker_result=worker_result, manifest=manifest)


def _package_for_workflow(conn, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
    row = conn.execute(
        "SELECT * FROM football_brief.p3_packages WHERE workflow_run_id = %s AND id = %s",
        (workflow_run_id, package_id),
    ).fetchone()
    if row is None:
        raise P3StepFiveError("package was not found for workflow")
    return dict(row)


def _approved_review_for_package(conn, workflow_run_id: UUID, package_id: UUID) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT * FROM football_brief.p3_package_reviews
        WHERE workflow_run_id = %s AND package_id = %s AND status = 'approved'
        """,
        (workflow_run_id, package_id),
    ).fetchone()
    if row is None:
        raise P3StepFiveError("package approval was not found")
    return dict(row)
