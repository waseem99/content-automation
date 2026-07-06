from __future__ import annotations

import pytest

from src.application.workers.hashing import worker_idempotency_key, worker_input_hash
from src.application.workers.models import WorkerExecutionRequest, WorkerOutcome
from src.domain.workflow_models import StageExecutionCreate
from src.domain.workflow_status import StageStatus
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import close_database, create_workflow, database_fixture
from tests.integration.worker_support import CountingWorker, definition, dispatcher


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_running_duplicate_does_not_execute_handler(database):
    workflow_id = create_workflow(database)
    worker = definition()
    payload = {"value": "same"}
    idem = worker_idempotency_key(worker, payload)
    ihash = worker_input_hash(worker, payload)
    with unit_of_work(database) as uow:
        stage = uow.stage_executions.create(
            StageExecutionCreate(
                workflow_run_id=workflow_id,
                stage_name=worker.name,
                stage_version=worker.version,
                idempotency_key=idem,
                input_hash=ihash,
                status=StageStatus.RUNNING,
                operator="pytest",
            )
        )
    service, handler = dispatcher(database, handler=CountingWorker(), worker_definition=worker)
    result = service.execute(
        WorkerExecutionRequest(workflow_run_id=workflow_id, worker_name=worker.name, worker_version=worker.version, input_payload=payload, actor="pytest")
    )
    assert result.outcome == WorkerOutcome.ALREADY_RUNNING
    assert result.stage_execution_id == stage.id
    assert handler.calls == 0
