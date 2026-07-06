from __future__ import annotations

import pytest

from src.application.workers.models import WorkerExecutionRequest, WorkerOutcome
from src.infrastructure.database.uow import unit_of_work
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


def test_external_call_row_is_reused_with_worker_result(database):
    workflow_id = create_workflow(database)
    service, handler = dispatcher(database)
    request = WorkerExecutionRequest(
        workflow_run_id=workflow_id,
        worker_name="demo_worker",
        worker_version="1",
        input_payload={"value": "ledger"},
        actor="pytest",
        provider="demo_provider",
        operation="demo_operation",
    )
    first = service.execute(request)
    second = service.execute(request)
    assert first.outcome == WorkerOutcome.SUCCEEDED
    assert second.outcome == WorkerOutcome.REUSED
    assert handler.calls == 1
    with unit_of_work(database) as uow:
        rows = uow.conn.execute(
            "SELECT * FROM football_brief.provider_calls WHERE provider = %s",
            ("demo_provider",),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["request_fingerprint"] == first.input_hash
    assert rows[0]["response_fingerprint"] == first.output_hash
