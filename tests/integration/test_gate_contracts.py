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


def _open_request(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id, status=StageStatus.RUNNING)
    request = OperatorGateService(database).request_gate(
        ReviewRequestCreate(
            workflow_run_id=workflow_id,
            stage_execution_id=stage.id,
            target_type=ReviewTargetType.STAGE,
            target_id=stage.id,
            review_type="stage_gate",
            requested_by="producer",
            reason="needs decision",
        )
    )
    return workflow_id, stage, request


def test_rationale_is_required(database):
    workflow_id, _, request = _open_request(database)
    with pytest.raises(RaiseException, match="rationale"):
        OperatorGateService(database).record_decision(
            ReviewDecisionCreate(
                workflow_run_id=workflow_id,
                review_request_id=request.id,
                review_type="stage_gate",
                decision=ReviewDecision.REJECTED,
                reviewer="reviewer-a",
                rationale=" ",
                checklist={"reviewed": True},
            )
        )


def test_checklist_is_required(database):
    workflow_id, _, request = _open_request(database)
    with pytest.raises(RaiseException, match="checklist"):
        OperatorGateService(database).record_decision(
            ReviewDecisionCreate(
                workflow_run_id=workflow_id,
                review_request_id=request.id,
                review_type="stage_gate",
                decision=ReviewDecision.REJECTED,
                reviewer="reviewer-a",
                rationale="Reviewed",
                checklist={},
            )
        )


def test_decision_rows_are_append_only(database):
    workflow_id, _, request = _open_request(database)
    decision = OperatorGateService(database).record_decision(
        ReviewDecisionCreate(
            workflow_run_id=workflow_id,
            review_request_id=request.id,
            review_type="stage_gate",
            decision=ReviewDecision.REJECTED,
            reviewer="reviewer-a",
            rationale="Reviewed",
            checklist={"reviewed": True},
        )
    )
    with pytest.raises(RaiseException, match="append-only"):
        with unit_of_work(database) as uow:
            uow.conn.execute("UPDATE football_brief.human_reviews SET rationale = 'changed' WHERE id = %s", (decision.id,))
