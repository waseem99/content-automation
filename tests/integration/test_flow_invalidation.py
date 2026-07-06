from __future__ import annotations

import pytest

from src.application.state_machine import WorkflowStateMachine
from src.domain.workflow_state_models import StageDependencyCreate, StageTransitionRequest, TransitionActorType, TransitionReasonCode
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


def test_upstream_hash_change_supersedes_downstream_stage(database):
    workflow_id = create_workflow(database)
    upstream = make_stage(database, workflow_id, name="upstream", status=StageStatus.RUNNING)
    downstream = make_stage(database, workflow_id, name="downstream", status=StageStatus.COMPLETED)
    machine = WorkflowStateMachine(database)
    machine.add_dependency(
        StageDependencyCreate(
            workflow_run_id=workflow_id,
            upstream_stage_execution_id=upstream.id,
            downstream_stage_execution_id=downstream.id,
            expected_upstream_output_hash="a" * 64,
            created_by="pytest",
        )
    )
    result = machine.transition_stage(
        StageTransitionRequest(
            stage_execution_id=upstream.id,
            target_status=StageStatus.COMPLETED,
            actor="worker",
            actor_type=TransitionActorType.WORKER,
            reason="changed output",
            output_hash="b" * 64,
        )
    )
    assert result["stale"]
    with unit_of_work(database) as uow:
        refreshed = uow.stage_executions.get(downstream.id)
    assert refreshed.status == StageStatus.SUPERSEDED
    assert refreshed.failure_reason == TransitionReasonCode.STALE_OUTPUT.value
