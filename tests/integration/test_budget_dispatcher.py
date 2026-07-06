from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.workers.models import WorkerExecutionRequest, WorkerOutcome
from src.domain.budget_models import BudgetLimit
from src.infrastructure.database.uow import unit_of_work
from tests.integration.budget_support import budgeted_dispatcher
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _request(workflow_id, value="image"):
    return WorkerExecutionRequest(
        workflow_run_id=workflow_id,
        worker_name="demo_worker",
        worker_version="1",
        input_payload={"value": value},
        actor="pytest",
        provider="openai",
        operation="image",
        provider_model_id="standard",
        provider_units=Decimal("1"),
    )


def test_successful_provider_worker_records_cost_and_reconciles(database):
    workflow_id = create_workflow(database)
    service, budget, handler = budgeted_dispatcher(database)
    result = service.execute(_request(workflow_id))
    assert result.outcome == WorkerOutcome.SUCCEEDED
    assert handler.calls == 1
    report = budget.reconcile_workflow_cost(workflow_id)
    assert report.cost_entry_total_usd == Decimal("0.0400")
    assert report.workflow_actual_cost_usd == Decimal("0.0400")
    assert report.matched is True
    with unit_of_work(database) as uow:
        provider_rows = uow.conn.execute("SELECT * FROM football_brief.provider_calls WHERE provider = 'openai'").fetchall()
        cost_rows = uow.conn.execute("SELECT * FROM football_brief.cost_entries WHERE workflow_run_id = %s", (workflow_id,)).fetchall()
    assert len(provider_rows) == 1
    assert len(cost_rows) == 1
    assert provider_rows[0]["cost_usd"] == Decimal("0.0400")


def test_duplicate_request_reuses_result_without_second_billable_row(database):
    workflow_id = create_workflow(database)
    service, _, handler = budgeted_dispatcher(database)
    first = service.execute(_request(workflow_id, value="same"))
    second = service.execute(_request(workflow_id, value="same"))
    assert first.outcome == WorkerOutcome.SUCCEEDED
    assert second.outcome == WorkerOutcome.REUSED
    assert handler.calls == 1
    with unit_of_work(database) as uow:
        provider_count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.provider_calls WHERE provider = 'openai'").fetchone()["count"]
        cost_count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.cost_entries WHERE workflow_run_id = %s", (workflow_id,)).fetchone()["count"]
    assert provider_count == 1
    assert cost_count == 1


def test_budget_stop_prevents_handler_execution_and_records_event(database):
    workflow_id = create_workflow(database)
    service, _, handler = budgeted_dispatcher(database, limits=BudgetLimit(workflow_limit_usd=Decimal("0.0100")))
    result = service.execute(_request(workflow_id, value="blocked"))
    assert result.outcome == WorkerOutcome.FAILED
    assert handler.calls == 0
    with unit_of_work(database) as uow:
        event = uow.conn.execute("SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'budget_stopped'", (workflow_id,)).fetchone()
        calls = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.provider_calls").fetchone()["count"]
    assert event is not None
    assert event["payload"]["reasons"] == ["WORKFLOW_LIMIT"]
    assert calls == 0


def test_premium_model_requires_operator_review_before_handler(database):
    workflow_id = create_workflow(database)
    service, _, handler = budgeted_dispatcher(database)
    request = _request(workflow_id, value="premium").model_copy(update={"provider_model_id": "premium"})
    result = service.execute(request)
    assert result.outcome == WorkerOutcome.HUMAN_REVIEW_REQUIRED
    assert handler.calls == 0
    with unit_of_work(database) as uow:
        event = uow.conn.execute("SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'budget_review_required'", (workflow_id,)).fetchone()
    assert event is not None
    assert event["payload"]["reasons"] == ["PREMIUM_REQUIRES_APPROVAL"]
