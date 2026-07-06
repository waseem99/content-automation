from __future__ import annotations

import pytest

from src.application.state_machine import StateMachineError, WorkflowStateMachine
from src.domain.workflow_state_models import StageTransitionRequest, TransitionActorType, TransitionReasonCode
from src.domain.workflow_status import StageStatus
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


def test_stage_transition_writes_event(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id)
    result = WorkflowStateMachine(database).transition_stage(
        StageTransitionRequest(
            stage_execution_id=stage.id,
            target_status=StageStatus.RUNNING,
            actor="worker",
            actor_type=TransitionActorType.WORKER,
            reason="claim",
        )
    )
    assert result["stage"]["status"] == "running"
    event = events_for(database, workflow_id)[-1]
    assert event["event_type"] == "stage_status_transition"
    assert event["from_status"] == "pending"
    assert event["to_status"] == "running"


def test_invalid_transition_returns_code(database):
    workflow_id = create_workflow(database)
    stage = make_stage(database, workflow_id)
    with pytest.raises(StateMachineError) as exc:
        WorkflowStateMachine(database).transition_stage(
            StageTransitionRequest(
                stage_execution_id=stage.id,
                target_status=StageStatus.COMPLETED,
                actor="worker",
                actor_type=TransitionActorType.WORKER,
                reason="not-running",
            )
        )
    assert exc.value.code == TransitionReasonCode.INVALID_TRANSITION
