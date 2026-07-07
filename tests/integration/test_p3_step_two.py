from __future__ import annotations

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools
from src.application.p3_step_one import P3StepOneService
from src.application.p3_step_two import P3StepTwoError, P3StepTwoService
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


def _option(database):
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
    packet_gate = ReviewPrerequisiteService(database)
    packet_gate.request_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, requested_by="pytest")
    packet_gate.set_packet_status(workflow_run_id=workflow_id, packet_id=packet.id, status="approved", reviewed_by="editor")
    output = StageProductService(database).create_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        actor="pytest",
    ).output
    assert output is not None
    OperatorReviewTools(database).approve_output(
        workflow_run_id=workflow_id,
        source_output_id=output.id,
        reviewed_by="producer",
    )
    plan = StepPlanService(database).create_for_output(
        workflow_run_id=workflow_id,
        source_output_id=output.id,
        actor="pytest",
    ).plan
    assert plan is not None
    step_one = P3StepOneService(database)
    requirement = step_one.materialize_requirements(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        actor="pytest",
    )[0]
    option = step_one.add_option(
        workflow_run_id=workflow_id,
        requirement_id=requirement["id"],
        reference_type="internal",
        reference_value="graphic-template-001",
        reference_metadata={"format": "png"},
        actor="pytest",
    )
    return workflow_id, option


def test_missing_and_pending_review_block_downstream_use(database) -> None:
    workflow_id, option = _option(database)
    service = P3StepTwoService(database)

    with pytest.raises(P3StepTwoError, match="missing"):
        service.require_approved(workflow_run_id=workflow_id, option_id=option["id"])

    review = service.request_review(workflow_run_id=workflow_id, option_id=option["id"], actor="pytest")
    assert review.status == "pending"

    with pytest.raises(P3StepTwoError, match="not approved"):
        service.require_approved(workflow_run_id=workflow_id, option_id=option["id"])

    pending = service.pending(workflow_id)
    assert [item.id for item in pending] == [review.id]


def test_approved_option_can_be_consumed(database) -> None:
    workflow_id, option = _option(database)
    service = P3StepTwoService(database)
    service.request_review(workflow_run_id=workflow_id, option_id=option["id"], actor="pytest")

    decision = service.decide(
        workflow_run_id=workflow_id,
        option_id=option["id"],
        status="approved",
        reviewed_by="producer",
        rationale="ready",
    )
    approved = service.require_approved(workflow_run_id=workflow_id, option_id=option["id"])

    assert decision.status == "approved"
    assert approved["id"] == option["id"]
    with unit_of_work(database) as uow:
        refreshed = uow.conn.execute("SELECT status FROM football_brief.p3_options WHERE id = %s", (option["id"],)).fetchone()
        events = [
            row["event_type"]
            for row in uow.conn.execute(
                "SELECT event_type FROM football_brief.workflow_events WHERE workflow_run_id = %s",
                (workflow_id,),
            ).fetchall()
        ]
    assert refreshed["status"] == "chosen"
    assert "p3_option_review_requested" in events
    assert "p3_option_review_decided" in events


def test_returned_option_cannot_be_consumed(database) -> None:
    workflow_id, option = _option(database)
    service = P3StepTwoService(database)

    decision = service.decide(
        workflow_run_id=workflow_id,
        option_id=option["id"],
        status="returned",
        reviewed_by="producer",
        rationale="needs replacement",
    )

    assert decision.status == "returned"
    with pytest.raises(P3StepTwoError, match="not approved"):
        service.require_approved(workflow_run_id=workflow_id, option_id=option["id"])
    with unit_of_work(database) as uow:
        refreshed = uow.conn.execute("SELECT status FROM football_brief.p3_options WHERE id = %s", (option["id"],)).fetchone()
    assert refreshed["status"] == "returned"


def test_wrong_workflow_and_invalid_status_fail_closed(database) -> None:
    workflow_id, option = _option(database)
    other_workflow_id = create_workflow(database)
    service = P3StepTwoService(database)

    with pytest.raises(P3StepTwoError, match="option"):
        service.request_review(workflow_run_id=other_workflow_id, option_id=option["id"], actor="pytest")

    with pytest.raises(P3StepTwoError, match="status"):
        service.decide(
            workflow_run_id=workflow_id,
            option_id=option["id"],
            status="pending",
            reviewed_by="producer",
        )
