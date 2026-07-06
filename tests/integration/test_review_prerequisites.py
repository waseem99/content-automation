from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteError, ReviewPrerequisiteService
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
        )
    ).intake
    packet = PacketService(database=database).create_for_intake(
        workflow_run_id=workflow_id,
        intake_id=intake.id,
        actor="pytest",
    ).packet
    assert packet is not None
    return workflow_id, packet


def test_pending_review_blocks_draft_prerequisite(database) -> None:
    workflow_id, packet = _packet(database)
    service = ReviewPrerequisiteService(database)

    review = service.request_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        requested_by="pytest",
    )

    assert review.created is True
    assert review.review.status == "pending"
    with pytest.raises(ReviewPrerequisiteError, match="not approved"):
        service.require_packet_approved(workflow_run_id=workflow_id, packet_id=packet.id)

    pending = service.pending_for_workflow(workflow_id)
    assert [item.id for item in pending] == [review.review.id]


def test_approved_review_allows_packet_for_draft_work(database) -> None:
    workflow_id, packet = _packet(database)
    service = ReviewPrerequisiteService(database)
    service.request_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, requested_by="pytest")

    decision = service.set_packet_status(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        status="approved",
        reviewed_by="editor",
        rationale="ready",
    )
    allowed = service.require_packet_approved(workflow_run_id=workflow_id, packet_id=packet.id)

    assert decision.status == "approved"
    assert decision.reviewed_by == "editor"
    assert allowed.id == packet.id

    with unit_of_work(database) as uow:
        event_types = [
            row["event_type"]
            for row in uow.conn.execute(
                "SELECT event_type FROM football_brief.workflow_events WHERE workflow_run_id = %s ORDER BY created_at",
                (workflow_id,),
            ).fetchall()
        ]
    assert "review_prerequisite_requested" in event_types
    assert "review_prerequisite_decided" in event_types


def test_changes_requested_or_missing_review_blocks_draft_work(database) -> None:
    workflow_id, packet = _packet(database)
    service = ReviewPrerequisiteService(database)

    with pytest.raises(ReviewPrerequisiteError, match="missing"):
        service.require_packet_approved(workflow_run_id=workflow_id, packet_id=packet.id)

    service.request_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, requested_by="pytest")
    service.set_packet_status(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        status="changes_requested",
        reviewed_by="editor",
        rationale="needs clearer source notes",
    )

    with pytest.raises(ReviewPrerequisiteError, match="not approved"):
        service.require_packet_approved(workflow_run_id=workflow_id, packet_id=packet.id)


def test_wrong_workflow_or_packet_fails_closed(database) -> None:
    workflow_id, packet = _packet(database)
    other_workflow_id = create_workflow(database)
    service = ReviewPrerequisiteService(database)

    with pytest.raises(ReviewPrerequisiteError, match="not found"):
        service.request_for_packet(workflow_run_id=other_workflow_id, packet_id=packet.id, requested_by="pytest")

    with pytest.raises(ReviewPrerequisiteError, match="not found"):
        service.request_for_packet(workflow_run_id=workflow_id, packet_id=uuid4(), requested_by="pytest")
