from __future__ import annotations

from uuid import UUID

from src.application.state_machine import WorkflowStateMachine
from src.domain.human_review_models import (
    HumanReview,
    ReviewDecision,
    ReviewDecisionCreate,
    ReviewHistory,
    ReviewRequest,
    ReviewRequestCreate,
    ReviewTargetType,
)
from src.domain.workflow_state_models import StageTransitionRequest, TransitionActorType
from src.domain.workflow_status import StageStatus
from src.infrastructure.database.connection import Database
from src.infrastructure.database.repository_operator_gates import OperatorGateDecisionRepository, OperatorGateRequestRepository
from src.infrastructure.database.uow import unit_of_work


class GateServiceError(RuntimeError):
    pass


class UnsafeGateDecision(GateServiceError):
    pass


POSITIVE_DECISIONS = {ReviewDecision.APPROVED, ReviewDecision.PASS, ReviewDecision.PASS_WITH_DISCLOSURE}


class OperatorGateService:
    def __init__(self, database: Database, state_machine: WorkflowStateMachine | None = None) -> None:
        self.database = database
        self.state_machine = state_machine or WorkflowStateMachine(database)

    def request_gate(self, data: ReviewRequestCreate) -> ReviewRequest:
        with unit_of_work(self.database) as uow:
            request = OperatorGateRequestRepository(uow.conn).create(data)
            uow.workflow_events.create(
                workflow_run_id=data.workflow_run_id,
                stage_execution_id=data.stage_execution_id,
                event_type="operator_gate_requested",
                actor=data.requested_by,
                reason=data.reason,
                payload={"request_id": str(request.id), "target_type": data.target_type.value, "target_id": str(data.target_id) if data.target_id else None},
            )
        if data.stage_execution_id is not None:
            self._move_stage_to_waiting(data.stage_execution_id, actor=data.requested_by, reason=data.reason)
        return request

    def record_decision(self, data: ReviewDecisionCreate) -> HumanReview:
        request = None
        if data.review_request_id:
            with unit_of_work(self.database) as uow:
                request = OperatorGateRequestRepository(uow.conn).get(data.review_request_id)
            data = data.model_copy(
                update={
                    "workflow_run_id": request.workflow_run_id,
                    "stage_execution_id": data.stage_execution_id or request.stage_execution_id,
                    "target_type": data.target_type or request.target_type,
                    "target_id": data.target_id or request.target_id,
                    "review_type": data.review_type or request.review_type,
                }
            )
        self._guard_positive_decision(data)
        with unit_of_work(self.database) as uow:
            decision = OperatorGateDecisionRepository(uow.conn).create(data)
            uow.workflow_events.create(
                workflow_run_id=data.workflow_run_id,
                stage_execution_id=data.stage_execution_id,
                event_type="operator_gate_decided",
                actor=data.reviewer,
                reason=data.decision.value,
                payload={"decision_id": str(decision.id), "request_id": str(data.review_request_id) if data.review_request_id else None},
            )
        stage_id = data.stage_execution_id or (request.stage_execution_id if request else None)
        if stage_id is not None:
            self._apply_stage_decision(stage_id, data)
        return decision

    def create_revision_attempt(self, stage_execution_id: UUID, *, actor: str, reason: str):
        return self.state_machine.retry_stage(stage_execution_id, actor=actor, reason=reason)

    def history_for_workflow(self, workflow_run_id: UUID) -> ReviewHistory:
        with unit_of_work(self.database) as uow:
            return OperatorGateDecisionRepository(uow.conn).history_for_workflow(workflow_run_id)

    def history_for_stage(self, stage_execution_id: UUID) -> tuple[HumanReview, ...]:
        with unit_of_work(self.database) as uow:
            return OperatorGateDecisionRepository(uow.conn).history_for_stage(stage_execution_id)

    def _move_stage_to_waiting(self, stage_execution_id: UUID, *, actor: str, reason: str) -> None:
        with unit_of_work(self.database) as uow:
            stage = uow.stage_executions.get(stage_execution_id)
        if stage.status == StageStatus.AWAITING_HUMAN:
            return
        if stage.status != StageStatus.RUNNING:
            raise GateServiceError("Only running stages can be gated")
        self.state_machine.transition_stage(
            StageTransitionRequest(stage_execution_id=stage_execution_id, target_status=StageStatus.AWAITING_HUMAN, actor=actor, actor_type=TransitionActorType.OPERATOR, reason=reason)
        )

    def _apply_stage_decision(self, stage_execution_id: UUID, data: ReviewDecisionCreate) -> None:
        with unit_of_work(self.database) as uow:
            stage = uow.stage_executions.get(stage_execution_id)
        if stage.status != StageStatus.AWAITING_HUMAN:
            raise GateServiceError("Stage is not awaiting operator decision")
        if data.decision in POSITIVE_DECISIONS:
            target = StageStatus.COMPLETED
        elif data.decision == ReviewDecision.CHANGES_REQUESTED:
            target = StageStatus.NEEDS_REVISION
        elif data.decision in {ReviewDecision.REJECTED, ReviewDecision.BLOCK}:
            target = StageStatus.REJECTED
        else:
            return
        self.state_machine.transition_stage(
            StageTransitionRequest(
                stage_execution_id=stage_execution_id,
                target_status=target,
                actor=data.reviewer,
                actor_type=TransitionActorType.OPERATOR,
                reason=data.decision.value,
                payload={"review_request_id": str(data.review_request_id) if data.review_request_id else None},
            )
        )

    def _guard_positive_decision(self, data: ReviewDecisionCreate) -> None:
        if data.decision not in POSITIVE_DECISIONS:
            return
        target_type = data.target_type
        target_id = data.target_id
        if target_type == ReviewTargetType.QUALITY_REPORT and target_id:
            with unit_of_work(self.database) as uow:
                row = uow.conn.execute("SELECT overall_status FROM football_brief.quality_reports WHERE id = %s", (target_id,)).fetchone()
            if row and row["overall_status"] == "block":
                raise UnsafeGateDecision("Cannot approve a blocking quality report")
        if target_type == ReviewTargetType.RIGHTS_GATE and target_id:
            with unit_of_work(self.database) as uow:
                row = uow.conn.execute("SELECT outcome FROM football_brief.rights_gate_evaluations WHERE id = %s", (target_id,)).fetchone()
            if row and row["outcome"] == "block":
                raise UnsafeGateDecision("Cannot approve a blocking rights evaluation")
