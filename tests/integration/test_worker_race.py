from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from src.application.workers.models import WorkerExecutionRequest, WorkerHandlerResult, WorkerOutcome
from src.infrastructure.database.uow import unit_of_work
from tests.integration.budget_support import budgeted_dispatcher
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


class SlowWorker:
    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, payload):
        with self._lock:
            self.calls += 1
        time.sleep(0.15)
        return WorkerHandlerResult(output={"value": payload["value"]}, units=Decimal("1"), metadata={"worker": "slow"})


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _request(workflow_id):
    return WorkerExecutionRequest(
        workflow_run_id=workflow_id,
        worker_name="demo_worker",
        worker_version="1",
        input_payload={"value": "same-concurrent-input"},
        actor="pytest",
        provider="openai",
        operation="image",
        provider_model_id="standard",
        provider_units=Decimal("1"),
    )


def test_duplicate_worker_requests_race_to_one_charged_row(database):
    workflow_id = create_workflow(database)
    handler = SlowWorker()
    service, _budget, _handler = budgeted_dispatcher(database, handler=handler)

    request = _request(workflow_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.execute(request), range(2)))

    outcomes = {result.outcome for result in results}
    assert WorkerOutcome.SUCCEEDED in outcomes
    assert outcomes <= {WorkerOutcome.SUCCEEDED, WorkerOutcome.REUSED, WorkerOutcome.ALREADY_RUNNING}
    assert handler.calls == 1

    with unit_of_work(database) as uow:
        provider_count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.provider_calls WHERE provider = 'openai'").fetchone()["count"]
        cost_count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.cost_entries WHERE workflow_run_id = %s", (workflow_id,)).fetchone()["count"]
    assert provider_count == 1
    assert cost_count == 1
