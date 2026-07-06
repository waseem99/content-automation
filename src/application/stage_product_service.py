from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.review_prerequisites import ReviewPrerequisiteService
from src.application.workers.dispatcher import WorkerDispatcher
from src.application.workers.models import WorkerDefinition, WorkerExecutionRequest, WorkerExecutionResult, WorkerHandlerResult, WorkerOutcome
from src.application.workers.registry import WorkerRegistry
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_packets import PacketRecord
from src.infrastructure.database.repository_stage_outputs import StageOutputRecord, StageOutputRepository
from src.infrastructure.database.uow import unit_of_work


@dataclass(frozen=True, slots=True)
class StageProductResult:
    worker_result: WorkerExecutionResult
    output: StageOutputRecord | None


def _outline(packet: PacketRecord) -> list[dict[str, Any]]:
    items = packet.extracted_claims or []
    if not items:
        return [{"section": "Main angle", "summary": "Manual football story angle", "citation_ids": []}]
    return [
        {
            "section": f"Point {index}",
            "summary": item.get("text", "Football story point"),
            "citation_ids": list(item.get("evidence_ids", [])),
        }
        for index, item in enumerate(items, start=1)
    ]


def _product_payload(packet: PacketRecord) -> dict[str, Any]:
    first = packet.extracted_claims[0].get("text", "story angle") if packet.extracted_claims else "story angle"
    outline = _outline(packet)
    narration = [
        {"order": index, "line": item["summary"], "citation_ids": item["citation_ids"]}
        for index, item in enumerate(outline, start=1)
    ]
    return {
        "title": ("Football brief: " + first)[:240],
        "hook": outline[0]["summary"] if outline else "Football story hook",
        "outline": outline,
        "narration": narration,
        "citation_map": packet.citations or [],
        "status": "review_required",
        "metadata": {"packet_hash": packet.packet_hash, "source_count": len(packet.source_metadata)},
    }


class StageProductWorker:
    def __init__(self, database: Database) -> None:
        self.database = database

    def __call__(self, payload: dict[str, Any]) -> WorkerHandlerResult:
        packet_id = UUID(payload["packet_id"])
        workflow_id = UUID(payload["workflow_run_id"])
        with unit_of_work(self.database) as uow:
            row = uow.conn.execute(
                "SELECT * FROM football_brief.research_packets WHERE id = %s AND workflow_run_id = %s",
                (packet_id, workflow_id),
            ).fetchone()
            if row is None:
                raise RuntimeError("packet was not found")
            packet = PacketRecord(**row)
        return WorkerHandlerResult(
            output=_product_payload(packet),
            units=Decimal("1"),
            unit_name="output",
            metadata={"mode": "deterministic", "packet_id": str(packet_id)},
        )


def stage_product_definition() -> WorkerDefinition:
    return WorkerDefinition(
        name="stage_product_worker",
        version="1",
        input_schema_name="StageProductInput",
        input_schema_version="1",
        output_schema_name="StageProduct",
        output_schema_version="1",
        timeout_seconds=60,
        estimated_cost_usd=Decimal("0.0000"),
        idempotency_fields=("workflow_run_id", "packet_id"),
    )


class StageProductService:
    def __init__(self, database: Database) -> None:
        self.database = database
        registry = WorkerRegistry()
        registry.register(stage_product_definition(), StageProductWorker(database))
        self.dispatcher = WorkerDispatcher(database=database, registry=registry)
        self.reviews = ReviewPrerequisiteService(database)

    def create_for_packet(self, *, workflow_run_id: UUID, packet_id: UUID, actor: str) -> StageProductResult:
        packet = self.reviews.require_packet_approved(workflow_run_id=workflow_run_id, packet_id=packet_id)
        worker_result = self.dispatcher.execute(
            WorkerExecutionRequest(
                workflow_run_id=workflow_run_id,
                worker_name="stage_product_worker",
                worker_version="1",
                input_payload={"workflow_run_id": str(workflow_run_id), "packet_id": str(packet_id)},
                actor=actor,
                stage_name="draft_output",
            )
        )
        if worker_result.outcome not in {WorkerOutcome.SUCCEEDED, WorkerOutcome.REUSED} or not worker_result.output or not worker_result.output_hash:
            return StageProductResult(worker_result=worker_result, output=None)

        data = worker_result.output
        with unit_of_work(self.database) as uow:
            output = StageOutputRepository(uow.conn).create(
                workflow_run_id=workflow_run_id,
                packet_id=packet_id,
                intake_id=packet.intake_id,
                stage_execution_id=worker_result.stage_execution_id,
                draft_hash=worker_result.output_hash,
                title=str(data["title"]),
                hook=str(data["hook"]),
                outline=list(data.get("outline", [])),
                narration=list(data.get("narration", [])),
                citation_map=list(data.get("citation_map", [])),
                metadata={"worker": worker_result.idempotency_key, "reused": worker_result.reused, **dict(data.get("metadata", {}))},
                created_by=actor,
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=worker_result.stage_execution_id,
                event_type="draft_output_created",
                actor=actor,
                reason="requires_human_review",
                payload={"output_id": str(output.id), "packet_id": str(packet_id), "status": output.status},
            )
        return StageProductResult(worker_result=worker_result, output=output)
