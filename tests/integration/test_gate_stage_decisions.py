from __future__ import annotations

import pytest
from psycopg.errors import RaiseException

from src.application.gates import OperatorGateService
from src.domain.human_review_models import ReviewDecision, ReviewDecisionCreate, ReviewRequestCreate, ReviewTargetType
from src.domain.workflow_status import StageStatus
from src.infrastructure.database.uow import unit_of_work
from tests.integration.flow_support import make_stage
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _request(database, workflow_id, stage_id, *, requested_by="producer"):
    return OperatorGateService(database).request_gate(
        ReviewRequestCreate(
            workflow_run_id=workflow_id,
            stage_execution_id=stage_id,
            target_type=ReviewTargetType.STAGE,
            target_id=stage_id,
            review_type="stage_gate",
            requested_by=requested_by,
            reason="needs operator decision",
            required_checklist={"checked": True},
        )
    )


def test_gate_request_moves_running_stage_to_waiting(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    request = _request(database, workflow_id, stage.id)
    with unit_of_work(database) as uow:
        refreshed = uow.stage_executions.get(stage.id)
    assert request.status.value == "open"
    assert refreshed.status == StageStatus.AWAITING_HUMAN


def test_positive_decision_completes_waiting_stage_and_keeps_history(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    service = OperatorGateService(database)
    request = _request(database, workflow_id, stage.id)
    decision = service.record_decision(
        ReviewDecisionCreate(
            workflow_run_id=workflow_id,
            review_request_id=request.id,
            review_type="stage_gate",
            decision=ReviewDecision.APPROVED,
            reviewer="reviewer-a",
            rationale="Checklist is complete",
            checklist={"safe": True},
        )
    )
    with unit_of_work(database) as uow:
        refreshed = uow.stage_executions.get(stage.id)
        req = uow.conn.execute("SELECT status FROM football_brief.human_review_requests WHERE id = %s", (request.id,)).fetchone()
    assert refreshed.status == StageStatus.COMPLETED
    assert req["status"] == "decided"
    assert service.history_for_workflow(workflow_id).decisions[-1].id == decision.id


def test_changes_requested_creates_revision_attempt(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    service = OperatorGateService(database)
    request = _request(database, workflow_id, stage.id)
    service.record_decision(
        ReviewDecisionCreate(
            workflow_run_id=workflow_id,
            review_request_id=request.id,
            review_type="stage_gate",
            decision=ReviewDecision.CHANGES_REQUESTED,
            reviewer="reviewer-a",
            rationale="Needs revision",
            checklist={"changes": True},
        )
    )
    with unit_of_work(database) as uow:
        refreshed = uow.stage_executions.get(stage.id)
    assert refreshed.status == StageStatus.NEEDS_REVISION
    retry = service.create_revision_attempt(stage.id, actor="producer", reason="apply requested changes")
    assert retry.id != stage.id
    assert retry.attempt == stage.attempt + 1
    assert retry.status == StageStatus.PENDING


def test_rejection_moves_stage_to_rejected(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    service = OperatorGateService(database)
    request = _request(database, workflow_id, stage.id)
    service.record_decision(
        ReviewDecisionCreate(
            workflow_run_id=workflow_id,
            review_request_id=request.id,
            review_type="stage_gate",
            decision=ReviewDecision.REJECTED,
            reviewer="reviewer-a",
            rationale="Not acceptable",
            checklist={"reviewed": True},
        )
    )
    with unit_of_work(database) as uow:
        refreshed = uow.stage_executions.get(stage.id)
    assert refreshed.status == StageStatus.REJECTED


def test_same_person_cannot_decide_own_request(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    request = _request(database, workflow_id, stage.id, requested_by="same-user")
    with pytest.raises(RaiseException, match="Self approval"):
        OperatorGateService(database).record_decision(
            ReviewDecisionCreate(
                workflow_run_id=workflow_id,
                review_request_id=request.id,
                review_type="stage_gate",
                decision=ReviewDecision.APPROVED,
                reviewer="same-user",
                rationale="Looks fine",
                checklist={"safe": True},
            )
        )
