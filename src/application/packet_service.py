from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.application.budget.service import BudgetControlService
from src.application.budget.worker_dispatcher import BudgetedWorkerDispatcher
from src.application.workers.models import WorkerDefinition, WorkerExecutionRequest, WorkerExecutionResult, WorkerHandlerResult, WorkerOutcome
from src.application.workers.registry import WorkerRegistry
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_intake import IntakeRepository, IntakeRecord
from src.infrastructure.database.repository_packets import PacketRecord, PacketRepository
from src.infrastructure.database.uow import unit_of_work


class PacketServiceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PacketBuildResult:
    worker_result: WorkerExecutionResult
    packet: PacketRecord | None


def _source_metadata(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "url": item["normalized_url"],
            "type": item.get("source_type", "url"),
            "captured_from": "manual_intake",
        }
        for item in refs
    ]


def _packet_output(intake: IntakeRecord, refs: list[dict[str, Any]]) -> dict[str, Any]:
    topic = intake.topic or "Untitled football topic"
    citations = [
        {"id": f"S{index}", "url": item["normalized_url"], "label": f"Source {index}"}
        for index, item in enumerate(refs, start=1)
    ]
    claim_text = topic if intake.topic else "Manual URL-backed football intake"
    return {
        "intake_id": str(intake.id),
        "topic": topic,
        "angle": intake.angle,
        "source_metadata": _source_metadata(refs),
        "extracted_claims": [
            {
                "id": "C1",
                "text": claim_text,
                "evidence_ids": [item["id"] for item in citations],
                "status": "draft_from_intake",
            }
        ],
        "quote_boundaries": [],
        "entities": intake.football_metadata,
        "freshness": {"mode": "manual", "source_count": len(refs), "created_at": intake.created_at.isoformat()},
        "citations": citations,
        "confidence_notes": "Deterministic manual packet from approved intake. External retrieval is not enabled in P2-02.",
    }


class ManualPacketWorker:
    def __init__(self, database: Database) -> None:
        self.database = database

    def __call__(self, payload: dict[str, Any]) -> WorkerHandlerResult:
        intake_id = UUID(payload["intake_id"])
        with unit_of_work(self.database) as uow:
            row = uow.conn.execute("SELECT * FROM football_brief.content_intakes WHERE id = %s", (intake_id,)).fetchone()
            if row is None:
                raise PacketServiceError("intake was not found")
            intake = IntakeRecord(**row)
            if intake.status != "accepted":
                raise PacketServiceError("intake is not accepted")
            refs = IntakeRepository(uow.conn).list_references(intake.id)
        return WorkerHandlerResult(
            output=_packet_output(intake, refs),
            units=Decimal("1"),
            unit_name="packet",
            metadata={"mode": "manual", "reference_count": len(refs)},
        )


def packet_worker_definition() -> WorkerDefinition:
    return WorkerDefinition(
        name="packet_worker",
        version="1",
        input_schema_name="PacketInput",
        input_schema_version="1",
        output_schema_name="PacketOutput",
        output_schema_version="1",
        timeout_seconds=60,
        estimated_cost_usd=Decimal("0.0100"),
        idempotency_fields=("intake_id", "workflow_run_id"),
    )


class PacketService:
    def __init__(self, *, database: Database, budget_control: BudgetControlService | None = None) -> None:
        self.database = database
        self.budget_control = budget_control or BudgetControlService(database=database)
        registry = WorkerRegistry()
        registry.register(packet_worker_definition(), ManualPacketWorker(database))
        self.dispatcher = BudgetedWorkerDispatcher(database=database, registry=registry, budget_control=self.budget_control)

    def create_for_intake(self, *, workflow_run_id: UUID, intake_id: UUID, actor: str) -> PacketBuildResult:
        with unit_of_work(self.database) as uow:
            intake_row = uow.conn.execute("SELECT * FROM football_brief.content_intakes WHERE id = %s AND workflow_run_id = %s", (intake_id, workflow_run_id)).fetchone()
            if intake_row is None:
                raise PacketServiceError("intake was not found for workflow")
            intake = IntakeRecord(**intake_row)
            if intake.status != "accepted":
                raise PacketServiceError("intake is not accepted")

        worker_result = self.dispatcher.execute(
            WorkerExecutionRequest(
                workflow_run_id=workflow_run_id,
                worker_name="packet_worker",
                worker_version="1",
                input_payload={"workflow_run_id": str(workflow_run_id), "intake_id": str(intake_id)},
                actor=actor,
                stage_name="research_packet",
                provider="serpapi",
                operation="search",
                provider_model_id="standard",
                provider_units=Decimal("1"),
            )
        )
        if worker_result.outcome not in {WorkerOutcome.SUCCEEDED, WorkerOutcome.REUSED} or not worker_result.output or not worker_result.output_hash:
            return PacketBuildResult(worker_result=worker_result, packet=None)

        output = worker_result.output
        with unit_of_work(self.database) as uow:
            packet = PacketRepository(uow.conn).create(
                workflow_run_id=workflow_run_id,
                intake_id=intake_id,
                stage_execution_id=worker_result.stage_execution_id,
                packet_hash=worker_result.output_hash,
                source_metadata=list(output.get("source_metadata", [])),
                extracted_claims=list(output.get("extracted_claims", [])),
                quote_boundaries=list(output.get("quote_boundaries", [])),
                entities=dict(output.get("entities", {})),
                freshness=dict(output.get("freshness", {})),
                citations=list(output.get("citations", [])),
                confidence_notes=output.get("confidence_notes"),
                provider_metadata={"worker": worker_result.idempotency_key, "reused": worker_result.reused},
                created_by=actor,
            )
            uow.workflow_events.create(
                workflow_run_id=workflow_run_id,
                stage_execution_id=worker_result.stage_execution_id,
                event_type="research_packet_created",
                actor=actor,
                reason="packet_persisted",
                payload={"packet_id": str(packet.id), "packet_hash": packet.packet_hash, "intake_id": str(intake_id)},
            )
        return PacketBuildResult(worker_result=worker_result, packet=packet)
