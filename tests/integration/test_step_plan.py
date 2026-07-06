from __future__ import annotations

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteService
from src.application.stage_product_service import StageProductService
from src.application.step_plan_service import StepPlanError, StepPlanReviewService, StepPlanService
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


def _source_output(database):
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
    packet_review = ReviewPrerequisiteService(database)
    packet_review.request_for_packet(workflow_run_id=workflow_id, packet_id=packet.id, requested_by="pytest")
    packet_review.set_packet_status(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        status="approved",
        reviewed_by="editor",
        rationale="ready",
    )
    output = StageProductService(database).create_for_packet(
        workflow_run_id=workflow_id,
        packet_id=packet.id,
        actor="pytest",
    ).output
    assert output is not None
    return workflow_id, output


def test_step_plan_requires_approved_source_output(database) -> None:
    workflow_id, output = _source_output(database)
    service = StepPlanService(database)

    with pytest.raises(StepPlanError, match="missing"):
        service.create_for_output(workflow_run_id=workflow_id, source_output_id=output.id, actor="pytest")

    review = StepPlanReviewService(database)
    review.request(workflow_run_id=workflow_id, source_output_id=output.id)

    with pytest.raises(StepPlanError, match="not approved"):
        service.create_for_output(workflow_run_id=workflow_id, source_output_id=output.id, actor="pytest")


def test_step_plan_creates_scene_and_requirement_rows(database) -> None:
    workflow_id, output = _source_output(database)
    review = StepPlanReviewService(database)
    review.request(workflow_run_id=workflow_id, source_output_id=output.id)
    review.approve(
        workflow_run_id=workflow_id,
        source_output_id=output.id,
        reviewed_by="producer",
        rationale="ready for planning",
    )

    result = StepPlanService(database).create_for_output(
        workflow_run_id=workflow_id,
        source_output_id=output.id,
        actor="pytest",
    )

    assert result.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert result.plan is not None
    assert result.plan.workflow_run_id == workflow_id
    assert result.plan.source_output_id == output.id
    assert result.plan.packet_id == output.packet_id
    assert result.plan.intake_id == output.intake_id
    assert result.plan.scenes[0]["narration_line"] == "Derby preview"
    assert result.plan.requirements[0]["needs_rights_review"] is True
    assert result.plan.requirements[0]["approved_asset_id"] is None
    assert result.plan.notes[0]["scope"] == "planning_only"

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'step_plan_created'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["plan_id"] == str(result.plan.id)


def test_step_plan_duplicate_request_reuses_existing_plan(database) -> None:
    workflow_id, output = _source_output(database)
    review = StepPlanReviewService(database)
    review.request(workflow_run_id=workflow_id, source_output_id=output.id)
    review.approve(workflow_run_id=workflow_id, source_output_id=output.id, reviewed_by="producer")
    service = StepPlanService(database)

    first = service.create_for_output(workflow_run_id=workflow_id, source_output_id=output.id, actor="pytest")
    second = service.create_for_output(workflow_run_id=workflow_id, source_output_id=output.id, actor="pytest")

    assert first.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert second.worker_result.outcome == WorkerOutcome.REUSED
    assert first.plan is not None and second.plan is not None
    assert second.plan.id == first.plan.id

    with unit_of_work(database) as uow:
        count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.step_plans").fetchone()["count"]
    assert count == 1
