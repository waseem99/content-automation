from __future__ import annotations

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteError, ReviewPrerequisiteService
from src.application.stage_product_service import StageProductService
from src.application.workers.models import WorkerOutcome
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


def _packet(database):
    workflow_id = create_workflow(database)
    intake = SourceIntakeService(database).create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            topic="Derby preview",
            source_urls=("https://example.com/story",),
            created_by="pytest",
            football_metadata={"team": "Arsenal"},
        )
    ).intake
    packet = PacketService(database=database).create_for_intake(
        workflow_run_id=workflow_id,
        intake_id=intake.id,
        actor="pytest",
    ).packet
    assert packet is not None
    return workflow_id, packet


def _approve(database, workflow_id, packet_id):
    review = ReviewPrerequisiteService(database)
    review.request_for_packet(workflow_run_id=workflow_id, packet_id=packet_id, requested_by="pytest")
    review.set_packet_status(
        workflow_run_id=workflow_id,
        packet_id=packet_id,
        status="approved",
        reviewed_by="editor",
        rationale="ready",
    )


def test_stage_product_requires_approved_packet(database) -> None:
    workflow_id, packet = _packet(database)

    with pytest.raises(ReviewPrerequisiteError, match="missing"):
        StageProductService(database).create_for_packet(
            workflow_run_id=workflow_id,
            packet_id=packet.id,
            actor="pytest",
        )

    review = ReviewPrerequisiteService(database)
    review.request_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, requested_by="pytest")
    with pytest.raises(ReviewPrerequisiteError, match="not approved"):
        StageProductService(database).create_for_packet(
            workflow_run_id=workflow_id,
            packet_id=packet.id,
            actor="pytest",
        )


def test_stage_product_creates_structured_output_and_review_required_state(database) -> None:
    workflow_id, packet = _packet(database)
    _approve(database, workflow_id, packet.id)

    result = StageProductService(database).create_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        actor="pytest",
    )

    assert result.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert result.output is not None
    assert result.output.workflow_run_id == workflow_id
    assert result.output.packet_id == packet.id
    assert result.output.intake_id == packet.intake_id
    assert result.output.status == "review_required"
    assert result.output.title.startswith("Football brief:")
    assert result.output.outline[0]["summary"] == "Derby preview"
    assert result.output.narration[0]["line"] == "Derby preview"
    assert result.output.citation_map[0]["id"] == "S1"

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'draft_output_created'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["status"] == "review_required"


def test_stage_product_duplicate_request_reuses_existing_output(database) -> None:
    workflow_id, packet = _packet(database)
    _approve(database, workflow_id, packet.id)
    service = StageProductService(database)

    first = service.create_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, actor="pytest")
    second = service.create_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, actor="pytest")

    assert first.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert second.worker_result.outcome == WorkerOutcome.REUSED
    assert first.output is not None and second.output is not None
    assert second.output.id == first.output.id

    with unit_of_work(database) as uow:
        count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.draft_outputs").fetchone()["count"]
    assert count == 1
