from __future__ import annotations

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteService, ReviewPrerequisiteError
from src.application.stage_product_service import StageProductService
from src.application.step_plan_service import StepPlanError, StepPlanService
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


def test_p2_end_to_end_flow_requires_reviews_and_surfaces_operator_queue(database) -> None:
    workflow_id = create_workflow(database)

    intake_result = SourceIntakeService(database).create(
        CreateIntakeRequest(
            workflow_run_id=workflow_id,
            topic="Derby preview",
            angle="Explain the key match narrative with cited claims.",
            source_urls=("https://example.com/story",),
            created_by="pytest",
            football_metadata={"team": "Arsenal", "competition": "Premier League"},
        )
    )
    intake = intake_result.intake
    assert intake_result.created is True

    packet_result = PacketService(database=database).create_for_intake(
        workflow_run_id=workflow_id,
        intake_id=intake.id,
        actor="pytest",
    )
    packet = packet_result.packet
    assert packet is not None
    assert packet_result.worker_result.outcome == WorkerOutcome.SUCCEEDED

    packet_reviews = ReviewPrerequisiteService(database)
    packet_review = packet_reviews.request_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        requested_by="pytest",
    )
    assert packet_review.review.status == "pending"

    with pytest.raises(ReviewPrerequisiteError):
        StageProductService(database).create_for_packet(
            workflow_run_id=workflow_id,
            packet_id=packet.id,
            actor="pytest",
        )

    packet_decision = OperatorReviewTools(database).approve_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        reviewed_by="editor",
        rationale="packet ready",
    )
    assert packet_decision.status == "approved"

    output_result = StageProductService(database).create_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        actor="pytest",
    )
    source_output = output_result.output
    assert source_output is not None
    assert source_output.status == "review_required"

    tools = OperatorReviewTools(database)
    queue_after_output = tools.queue(workflow_id)
    assert [item.item_type for item in queue_after_output] == ["source_output_review"]

    with pytest.raises(StepPlanError):
        StepPlanService(database).create_for_output(
            workflow_run_id=workflow_id,
            source_output_id=source_output.id,
            actor="pytest",
        )

    output_decision = tools.approve_output(
        workflow_run_id=workflow_id,
        source_output_id=source_output.id,
        reviewed_by="producer",
        rationale="output ready for planning",
    )
    assert output_decision.status == "approved"

    plan_result = StepPlanService(database).create_for_output(
        workflow_run_id=workflow_id,
        source_output_id=source_output.id,
        actor="pytest",
    )
    plan = plan_result.plan
    assert plan is not None
    assert plan.scenes
    assert plan.requirements[0]["needs_rights_review"] is True
    assert plan.requirements[0]["approved_asset_id"] is None

    final_queue = tools.queue(workflow_id)
    assert [item.item_type for item in final_queue] == ["plan_review"]
    assert final_queue[0].id == plan.id

    with unit_of_work(database) as uow:
        event_types = {
            row["event_type"]
            for row in uow.conn.execute(
                "SELECT event_type FROM football_brief.workflow_events WHERE workflow_run_id = %s",
                (workflow_id,),
            ).fetchall()
        }
    assert {
        "content_intake_created",
        "research_packet_created",
        "review_prerequisite_requested",
        "review_prerequisite_decided",
        "draft_output_created",
        "source_output_review_requested",
        "source_output_review_approved",
        "step_plan_created",
    }.issubset(event_types)
