from __future__ import annotations

import pytest

from src.application.state_machine import WorkflowStateMachine
from src.domain.workflow_status import StageStatus
from src.infrastructure.database.uow import unit_of_work
from tests.integration.flow_support import events_for, make_stage
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_retry_creates_new_attempt_and_preserves_old_stage(database):
    workflow_id = create_workflow(database)
    failed = make_stage(database, workflow_id, name="retry", status=StageStatus.FAILED)
    retry = WorkflowStateMachine(database).retry_stage(failed.id, actor="operator", reason="try again")
    assert retry.id != failed.id
    assert retry.attempt == failed.attempt + 1
    assert retry.status == StageStatus.PENDING
    with unit_of_work(database) as uow:
        old = uow.stage_executions.get(failed.id)
    assert old.status == StageStatus.FAILED
    assert events_for(database, workflow_id)[-1]["event_type"] == "stage_retry_created"


def test_resume_plan_skips_completed_and_runs_invalid_stages(database):
    workflow_id = create_workflow(database)
    completed = make_stage(database, workflow_id, name="done", status=StageStatus.COMPLETED)
    failed = make_stage(database, workflow_id, name="failed", status=StageStatus.FAILED)
    pending = make_stage(database, workflow_id, name="pending", status=StageStatus.PENDING)
    waiting = make_stage(database, workflow_id, name="waiting", status=StageStatus.AWAITING_HUMAN)
    plan = WorkflowStateMachine(database).resume_plan(workflow_id)
    assert completed.id in plan.skipped_stage_ids
    assert failed.id in plan.runnable_stage_ids
    assert pending.id in plan.runnable_stage_ids
    assert waiting.id in plan.blocked_stage_ids
