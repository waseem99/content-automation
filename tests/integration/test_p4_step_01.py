from __future__ import annotations

import pytest

from src.application.operator_review_tools import OperatorReviewTools
from src.application.p4_control import P4ControlRequest, P4ControlService
from src.application.step_plan_service import StepPlanReviewService
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _request(workflow_id):
    return P4ControlRequest(
        workflow_run_id=workflow_id,
        topic="Derby preview",
        source_urls=("https://example.com/story",),
        actor="pytest",
    )


def test_p4_control_starts_and_waits_for_packet_review(database) -> None:
    workflow_id = create_workflow(database)
    result = P4ControlService(database).run_until_waiting(_request(workflow_id))

    assert result.status == "waiting"
    assert result.next_action == "approve_packet"
    assert [step.name for step in result.steps] == ["intake", "packet", "packet_review"]
    assert result.steps[-1].status == "waiting"


def test_p4_control_resumes_after_packet_approval_and_waits_for_output_review(database) -> None:
    workflow_id = create_workflow(database)
    service = P4ControlService(database)
    first = service.run_until_waiting(_request(workflow_id))
    packet_id = first.steps[1].resource_id
    assert packet_id is not None

    OperatorReviewTools(database).approve_packet(workflow_run_id=workflow_id, packet_id=packet_id, reviewed_by="editor")
    second = service.run_until_waiting(_request(workflow_id))

    assert second.status == "waiting"
    assert second.next_action == "approve_output"
    assert [step.name for step in second.steps][-1] == "source_output_review"


def test_p4_control_resumes_after_output_approval_and_creates_step_plan(database) -> None:
    workflow_id = create_workflow(database)
    service = P4ControlService(database)
    first = service.run_until_waiting(_request(workflow_id))
    packet_id = first.steps[1].resource_id
    assert packet_id is not None
    OperatorReviewTools(database).approve_packet(workflow_run_id=workflow_id, packet_id=packet_id, reviewed_by="editor")
    second = service.run_until_waiting(_request(workflow_id))
    output_id = second.steps[3].resource_id
    assert output_id is not None
    OperatorReviewTools(database).approve_output(workflow_run_id=workflow_id, source_output_id=output_id, reviewed_by="producer")

    third = service.run_until_waiting(_request(workflow_id))

    assert third.status == "waiting"
    assert third.next_action == "continue_p3_delivery"
    assert third.steps[-1].name == "step_plan"
    assert third.steps[-1].status == "done"


def test_p4_control_result_is_json_friendly(database) -> None:
    workflow_id = create_workflow(database)
    result = P4ControlService(database).run_until_waiting(_request(workflow_id)).as_dict()

    assert result["workflow_run_id"] == str(workflow_id)
    assert result["status"] == "waiting"
    assert result["steps"][0]["name"] == "intake"
    assert isinstance(result["steps"][0]["metadata"], dict)
