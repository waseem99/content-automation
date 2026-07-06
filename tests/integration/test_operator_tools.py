from __future__ import annotations

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteService
from src.application.stage_product_service import StageProductService
from src.application.step_plan_service import StepPlanService
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


def _output(database):
    workflow_id, packet = _packet(database)
    gate = ReviewPrerequisiteService(database)
    gate.request_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, requested_by="pytest")
    gate.set_packet_status(workflow_run_id=workflow_id, packet_id=packet.id, status="approved", reviewed_by="editor")
    output = StageProductService(database).create_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        actor="pytest",
    ).output
    assert output is not None
    return workflow_id, output


def test_queue_shows_pending_packet_item(database) -> None:
    workflow_id, packet = _packet(database)
    ReviewPrerequisiteService(database).request_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        requested_by="pytest",
    )

    items = OperatorReviewTools(database).queue(workflow_id)

    assert len(items) == 1
    assert items[0].item_type == "packet_review"
    assert items[0].id == packet.id
    assert items[0].status == "pending"
    assert items[0].metadata["intake_id"] == str(packet.intake_id)


def test_packet_approval_removes_packet_item(database) -> None:
    workflow_id, packet = _packet(database)
    ReviewPrerequisiteService(database).request_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        requested_by="pytest",
    )
    tools = OperatorReviewTools(database)

    decision = tools.approve_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        reviewed_by="editor",
        rationale="ready",
    )

    assert decision.status == "approved"
    assert tools.queue(workflow_id) == []


def test_queue_shows_unmarked_output_item(database) -> None:
    workflow_id, output = _output(database)

    items = OperatorReviewTools(database).queue(workflow_id)

    assert len(items) == 1
    assert items[0].item_type == "source_output_review"
    assert items[0].id == output.id
    assert items[0].status == "missing"
    assert items[0].metadata["packet_id"] == str(output.packet_id)


def test_output_approval_enables_plan_and_plan_item(database) -> None:
    workflow_id, output = _output(database)
    tools = OperatorReviewTools(database)

    output_gate = tools.approve_output(
        workflow_run_id=workflow_id,
        source_output_id=output.id,
        reviewed_by="producer",
        rationale="ready",
    )
    plan = StepPlanService(database).create_for_output(
        workflow_run_id=workflow_id,
        source_output_id=output.id,
        actor="pytest",
    ).plan

    assert output_gate.status == "approved"
    assert plan is not None
    items = tools.queue(workflow_id)
    assert len(items) == 1
    assert items[0].item_type == "plan_review"
    assert items[0].id == plan.id
    assert items[0].status == "review_required"
    assert items[0].metadata["source_output_id"] == str(output.id)

    with unit_of_work(database) as uow:
        event_types = [
            row["event_type"]
            for row in uow.conn.execute(
                "SELECT event_type FROM football_brief.workflow_events WHERE workflow_run_id = %s",
                (workflow_id,),
            ).fetchall()
        ]
    assert "source_output_review_requested" in event_types
    assert "source_output_review_approved" in event_types
