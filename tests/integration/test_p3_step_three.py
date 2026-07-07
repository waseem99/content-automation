from __future__ import annotations

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools
from src.application.p3_step_one import P3StepOneService
from src.application.p3_step_three import P3PackageService, P3PlanReviewService, P3StepThreeError
from src.application.p3_step_two import P3StepTwoError, P3StepTwoService
from src.application.packet_service import PacketService
from src.application.review_prerequisites import ReviewPrerequisiteService
from src.application.stage_product_service import StageProductService
from src.application.step_plan_service import StepPlanService
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


def _plan_and_option(database):
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
    return workflow_id, plan, option


def test_missing_plan_approval_blocks_package_creation(database) -> None:
    workflow_id, plan, option = _plan_and_option(database)
    P3StepTwoService(database).decide(
        workflow_run_id=workflow_id,
        option_id=option["id"],
        status="approved",
        reviewed_by="producer",
    )

    with pytest.raises(P3StepThreeError, match="step plan approval"):
        P3PackageService(database).create_for_plan(
            workflow_run_id=workflow_id,
            step_plan_id=plan.id,
            option_ids=[option["id"]],
            actor="pytest",
        )


def test_missing_option_approval_blocks_package_creation(database) -> None:
    workflow_id, plan, option = _plan_and_option(database)
    P3PlanReviewService(database).decide(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        status="approved",
        reviewed_by="producer",
    )

    with pytest.raises(P3StepTwoError, match="missing"):
        P3PackageService(database).create_for_plan(
            workflow_run_id=workflow_id,
            step_plan_id=plan.id,
            option_ids=[option["id"]],
            actor="pytest",
        )


def test_package_prep_creates_traceable_package(database) -> None:
    workflow_id, plan, option = _plan_and_option(database)
    P3PlanReviewService(database).request_review(workflow_run_id=workflow_id, step_plan_id=plan.id, actor="pytest")
    P3PlanReviewService(database).decide(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        status="approved",
        reviewed_by="producer",
        rationale="plan ready",
    )
    option_gate = P3StepTwoService(database)
    option_gate.request_review(workflow_run_id=workflow_id, option_id=option["id"], actor="pytest")
    option_gate.decide(
        workflow_run_id=workflow_id,
        option_id=option["id"],
        status="approved",
        reviewed_by="producer",
        rationale="safe option",
    )

    result = P3PackageService(database).create_for_plan(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        option_ids=[option["id"]],
        actor="pytest",
    )

    assert result.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert result.package is not None
    assert result.package.workflow_run_id == workflow_id
    assert result.package.step_plan_id == plan.id
    assert result.package.option_ids == [str(option["id"])]
    assert result.package.scene_map[0]["approved_option_id"] == str(option["id"])
    assert result.package.lineage_refs["step_plan_id"] == str(plan.id)
    assert result.package.metadata["option_count"] == 1

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'p3_package_created'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["package_id"] == str(result.package.id)


def test_duplicate_package_request_reuses_existing_package(database) -> None:
    workflow_id, plan, option = _plan_and_option(database)
    P3PlanReviewService(database).decide(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        status="approved",
        reviewed_by="producer",
    )
    P3StepTwoService(database).decide(
        workflow_run_id=workflow_id,
        option_id=option["id"],
        status="approved",
        reviewed_by="producer",
    )
    service = P3PackageService(database)

    first = service.create_for_plan(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        option_ids=[option["id"]],
        actor="pytest",
    )
    second = service.create_for_plan(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        option_ids=[option["id"]],
        actor="pytest",
    )

    assert first.worker_result.outcome == WorkerOutcome.SUCCEEDED
    assert second.worker_result.outcome == WorkerOutcome.REUSED
    assert first.package is not None and second.package is not None
    assert second.package.id == first.package.id
    with unit_of_work(database) as uow:
        count = uow.conn.execute("SELECT COUNT(*) AS count FROM football_brief.p3_packages").fetchone()["count"]
    assert count == 1


def test_wrong_workflow_inputs_fail_closed(database) -> None:
    workflow_id, plan, option = _plan_and_option(database)
    other_workflow_id = create_workflow(database)

    with pytest.raises(P3StepThreeError, match="step plan"):
        P3PlanReviewService(database).request_review(
            workflow_run_id=other_workflow_id,
            step_plan_id=plan.id,
            actor="pytest",
        )

    P3PlanReviewService(database).decide(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        status="approved",
        reviewed_by="producer",
    )
    with pytest.raises(P3StepTwoError, match="option"):
        P3PackageService(database).create_for_plan(
            workflow_run_id=other_workflow_id,
            step_plan_id=plan.id,
            option_ids=[option["id"]],
            actor="pytest",
        )
