from __future__ import annotations

import pytest

from src.application.workers.models import WorkerExecutionRequest, WorkerOutcome
from tests.integration.rights_support import close_database, create_workflow, database_fixture
from tests.integration.worker_support import dispatcher


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_worker_success_creates_stage_and_reuses_result(database):
    workflow_id = create_workflow(database)
    service, handler = dispatcher(database)
    request = WorkerExecutionRequest(
        workflow_run_id=workflow_id,
        worker_name="demo_worker",
        worker_version="1",
        input_payload={"value": "same"},
        actor="pytest",
    )
    first = service.execute(request)
    second = service.execute(request)
    assert first.outcome == WorkerOutcome.SUCCEEDED
    assert second.outcome == WorkerOutcome.REUSED
    assert second.stage_execution_id == first.stage_execution_id
    assert handler.calls == 1


def test_different_worker_version_gets_different_key(database):
    workflow_id = create_workflow(database)
    service1, _ = dispatcher(database)
    service2, _ = dispatcher(database, worker_definition=__import__("tests.integration.worker_support", fromlist=["definition"]).definition(version="2"))
    first = service1.execute(
        WorkerExecutionRequest(workflow_run_id=workflow_id, worker_name="demo_worker", worker_version="1", input_payload={"value": "same"}, actor="pytest")
    )
    second = service2.execute(
        WorkerExecutionRequest(workflow_run_id=workflow_id, worker_name="demo_worker", worker_version="2", input_payload={"value": "same"}, actor="pytest")
    )
    assert first.idempotency_key != second.idempotency_key
    assert first.stage_execution_id != second.stage_execution_id
