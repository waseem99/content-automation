from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.budget.service import BudgetControlService
from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.packet_service import PacketService, PacketServiceError
from src.application.workers.models import WorkerOutcome
from src.domain.budget_models import BudgetLimit
from src.infrastructure.database.uow import unit_of_work
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _intake(database, workflow_id, *, topic="Derby preview", url="https://example.com/story"):
    return SourceIntakeService(database).create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            topic=topic,
            angle="tactical story",
            source_urls=(url,),
            created_by="pytest",
            football_metadata={"team": "Arsenal", "league": "Premier League"},
        )
    ).intake


def test_builder_creates_persisted_brief_from_intake(database) -> None:
    workflow_id = create_workflow(database)
    intake = _intake(database, workflow_id)

    result = PacketService(database=database).create_for_intake(
        workflow_run_id=workflow_id,
        intake_id=intake.id,
        actor="pytest",
    )

    assert result.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert result.packet is not None
    assert result.packet.intake_id == intake.id
    assert result.packet.source_metadata[0]["url"] == "https://example.com/story"
    assert result.packet.extracted_claims[0]["text"] == "Derby preview"
    assert result.packet.citations[0]["id"] == "S1"
    assert result.packet.freshness["mode"] == "manual"
    assert result.packet.entities["team"] == "Arsenal"

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'research_packet_created'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["packet_id"] == str(result.packet.id)


def test_duplicate_builder_request_reuses_output_and_cost(database) -> None:
    workflow_id = create_workflow(database)
    intake = _intake(database, workflow_id)
    service = PacketService(database=database)

    first = service.create_for_intake(workflow_run_id=workflow_id, intake_id=intake.id, actor="pytest")
    second = service.create_for_intake(workflow_run_id=workflow_id, intake_id=intake.id, actor="pytest")

    assert first.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert second.worker_result.outcome == WorkerOutcome.REUSED
    assert first.packet is not None and second.packet is not None
    assert second.packet.id == first.packet.id

    with unit_of_work(database) as uow:
        provider_calls = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.provider_calls").fetchone()["count"]
        cost_entries = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.cost_entries").fetchone()["count"]
        workflow = uow.workflow_runs.get(workflow_id)
    assert provider_calls == 1
    assert cost_entries == 1
    assert workflow.actual_cost_usd == Decimal("0.0100")


def test_missing_or_rejected_intake_fails_closed(database) -> None:
    workflow_id = create_workflow(database)
    service = PacketService(database=database)

    with pytest.raises(PacketServiceError, match="not found"):
        service.create_for_intake(workflow_run_id=workflow_id, intake_id=uuid4(), actor="pytest")

    intake = _intake(database, workflow_id, topic="Rejected topic", url="https://example.com/rejected")
    with unit_of_work(database) as uow:
        uow.conn.execute("UPDATE football_brief.content_intakes SET status = 'rejected' WHERE id = %s", (intake.id,))

    with pytest.raises(PacketServiceError, match="not accepted"):
        service.create_for_intake(workflow_run_id=workflow_id, intake_id=intake.id, actor="pytest")


def test_budget_stop_prevents_brief_persistence(database) -> None:
    workflow_id = create_workflow(database)
    intake = _intake(database, workflow_id)
    service = PacketService(
        database=database,
        budget_control=BudgetControlService(database=database, limits=BudgetLimit(workflow_limit_usd=Decimal("0.0001"))),
    )

    result = service.create_for_intake(workflow_run_id=workflow_id, intake_id=intake.id, actor="pytest")

    assert result.worker_result.outcome == WorkerOutcome.FAILED
    assert result.packet is None
    with unit_of_work(database) as uow:
        table = "football_brief." + "research_" + "packets"
        packet_count = uow.conn.execute("SELECT COUNT(*) AS count FROM " + table).fetchone()["count"]
        budget_event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'budget_stopped'",
            (workflow_id,),
        ).fetchone()
    assert packet_count == 0
    assert budget_event is not None
