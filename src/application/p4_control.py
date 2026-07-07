from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteService
from src.application.stage_product_service import StageProductService
from src.application.step_plan_service import StepPlanReviewService, StepPlanService
from src.infrastructure.database.connection import Database


class P4ControlError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class P4ControlRequest:
    workflow_run_id: UUID
    topic: str
    source_urls: tuple[str, ...]
    actor: str = "operator"


@dataclass(frozen=True, slots=True)
class P4ControlStep:
    name: str
    status: str
    resource_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class P4ControlResult:
    workflow_run_id: UUID
    status: str
    next_action: str | None
    steps: list[P4ControlStep]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_run_id": str(self.workflow_run_id),
            "status": self.status,
            "next_action": self.next_action,
            "steps": [
                {"name": step.name, "status": step.status, "resource_id": step.resource_id, "reason": step.reason, "metadata": step.metadata or {}}
                for step in self.steps
            ],
        }


class P4ControlService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def run_until_waiting(self, request: P4ControlRequest) -> P4ControlResult:
        steps: list[P4ControlStep] = []
        intake_result = SourceIntakeService(self.database).create(
            CreateIntakeRequest(
                workflow_run_id=request.workflow_run_id,
                topic=request.topic,
                source_urls=request.source_urls,
                created_by=request.actor,
            )
        )
        intake = intake_result.intake
        steps.append(P4ControlStep("intake", "done", str(intake.id), metadata={"created": intake_result.created}))

        packet_result = PacketService(database=self.database).create_for_intake(
            workflow_run_id=request.workflow_run_id,
            intake_id=intake.id,
            actor=request.actor,
        )
        if packet_result.packet is None:
            return P4ControlResult(request.workflow_run_id, "error", None, [*steps, P4ControlStep("packet", "error")])
        packet = packet_result.packet
        steps.append(P4ControlStep("packet", "done", str(packet.id), metadata={"outcome": packet_result.worker_result.outcome.value}))

        packet_review = ReviewPrerequisiteService(self.database).request_for_packet(
            workflow_run_id=request.workflow_run_id,
            packet_id=packet.id,
            requested_by=request.actor,
        ).review
        if packet_review.status != "approved":
            return P4ControlResult(request.workflow_run_id, "waiting", "approve_packet", [*steps, P4ControlStep("packet_review", "waiting", str(packet_review.id), packet_review.status)])
        steps.append(P4ControlStep("packet_review", "done", str(packet_review.id), "approved"))

        output_result = StageProductService(self.database).create_for_packet(
            workflow_run_id=request.workflow_run_id,
            packet_id=packet.id,
            actor=request.actor,
        )
        if output_result.output is None:
            return P4ControlResult(request.workflow_run_id, "error", None, [*steps, P4ControlStep("source_output", "error")])
        output = output_result.output
        steps.append(P4ControlStep("source_output", "done", str(output.id), metadata={"outcome": output_result.worker_result.outcome.value}))

        output_review = StepPlanReviewService(self.database).request(
            workflow_run_id=request.workflow_run_id,
            source_output_id=output.id,
        )
        if output_review.status != "approved":
            return P4ControlResult(request.workflow_run_id, "waiting", "approve_output", [*steps, P4ControlStep("source_output_review", "waiting", str(output_review.id), output_review.status)])
        steps.append(P4ControlStep("source_output_review", "done", str(output_review.id), "approved"))

        plan_result = StepPlanService(self.database).create_for_output(
            workflow_run_id=request.workflow_run_id,
            source_output_id=output.id,
            actor=request.actor,
        )
        if plan_result.plan is None:
            return P4ControlResult(request.workflow_run_id, "error", None, [*steps, P4ControlStep("step_plan", "error")])
        steps.append(P4ControlStep("step_plan", "done", str(plan_result.plan.id), metadata={"outcome": plan_result.worker_result.outcome.value}))
        return P4ControlResult(request.workflow_run_id, "waiting", "continue_p3_delivery", steps)
