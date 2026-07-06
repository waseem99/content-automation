from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.intake_service import CreateIntakeRequest, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools
from src.application.p3_step_one import P3StepOneError, P3StepOneService
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


def _plan(database):
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
    return workflow_id, plan


def test_materialize_requirements_from_step_plan(database) -> None:
    workflow_id, plan = _plan(database)

    rows = P3StepOneService(database).materialize_requirements(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        actor="pytest",
    )

    assert len(rows) == len(plan.requirements)
    assert rows[0]["workflow_run_id"] == workflow_id
    assert rows[0]["step_plan_id"] == plan.id
    assert rows[0]["requirement_index"] == 1
    assert rows[0]["status"] == "open"
    assert rows[0]["metadata"]["needs_rights_review"] is True

    listed = P3StepOneService(database).list_requirements(plan.id)
    assert [row["id"] for row in listed] == [row["id"] for row in rows]

    with unit_of_work(database) as uow:
        event = uow.conn.execute(
            "SELECT * FROM football_brief.workflow_events WHERE workflow_run_id = %s AND event_type = 'p3_requirements_materialized'",
            (workflow_id,),
        ).fetchone()
    assert event is not None
    assert event["payload"]["requirement_count"] == len(rows)


def test_add_option_and_reuse_duplicate(database) -> None:
    workflow_id, plan = _plan(database)
    service = P3StepOneService(database)
    requirement = service.materialize_requirements(
        workflow_run_id=workflow_id,
        step_plan_id=plan.id,
        actor="pytest",
    )[0]

    first = service.add_option(
        workflow_run_id=workflow_id,
        requirement_id=requirement["id"],
        reference_type="internal",
        reference_value="graphic-template-001",
        reference_metadata={"format": "png"},
        notes="safe original graphic",
        actor="pytest",
    )
    second = service.add_option(
        workflow_run_id=workflow_id,
        requirement_id=requirement["id"],
        reference_type="internal",
        reference_value="graphic-template-001",
        reference_metadata={"format": "png"},
        notes="safe original graphic",
        actor="pytest",
    )

    assert second["id"] == first["id"]
    assert second["option_hash"] == first["option_hash"]
    options = service.list_options(requirement["id"])
    assert len(options) == 1

    refreshed = service.list_requirements(plan.id)[0]
    assert refreshed["status"] == "option_added"


def test_invalid_links_fail_closed(database) -> None:
    workflow_id, plan = _plan(database)
    other_workflow_id = create_workflow(database)
    service = P3StepOneService(database)

    with pytest.raises(P3StepOneError, match="step plan"):
        service.materialize_requirements(
            workflow_run_id=other_workflow_id,
            step_plan_id=plan.id,
            actor="pytest",
        )

    with pytest.raises(P3StepOneError, match="requirement"):
        service.add_option(
            workflow_run_id=workflow_id,
            requirement_id=uuid4(),
            reference_type="internal",
            reference_value="missing",
            actor="pytest",
        )

    with pytest.raises(P3StepOneError, match="required"):
        service.add_option(
            workflow_run_id=workflow_id,
            requirement_id=uuid4(),
            reference_type=" ",
            reference_value=" ",
            actor="pytest",
        )
