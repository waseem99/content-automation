from __future__ import annotations

import pytest

from src.application.p4_demo_flow import P4_DEMO_FLOW, P4DemoFlowService
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_demo_data_shape(database) -> None:
    scenario = P4DemoFlowService(database).scenario()

    assert scenario["ok"] is True
    assert scenario["scenario_id"] == "p4-demo-flow"
    assert scenario["topic"] == P4_DEMO_FLOW.topic
    assert scenario["source_urls"] == list(P4_DEMO_FLOW.source_urls)
    assert all(url.startswith("https://example.com/p4-demo/") for url in scenario["source_urls"])
    assert scenario["expected_stop_points"] == ["approve_packet", "approve_output", "continue_p3_delivery"]


def test_demo_reaches_first_stop_point(database) -> None:
    workflow_id = create_workflow(database)
    service = P4DemoFlowService(database)

    state = service.start(workflow_run_id=workflow_id)

    assert state["ok"] is True
    assert state["next_action"] == "approve_packet"
    assert state["current_step"]["name"] == "packet_review"
    status = service.status(workflow_run_id=workflow_id)
    assert status["ok"] is True
    assert status["queue"]["cards"][0]["item_type"] == "packet_review"


def test_demo_advances_through_supported_gates(database) -> None:
    workflow_id = create_workflow(database)
    service = P4DemoFlowService(database)

    first = service.start(workflow_run_id=workflow_id)
    assert first["next_action"] == "approve_packet"
    first_result = service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-editor")
    assert first_result["ok"] is True
    assert first_result["action"] == "approve_packet"

    second = service.start(workflow_run_id=workflow_id)
    assert second["next_action"] == "approve_output"
    second_result = service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")
    assert second_result["ok"] is True
    assert second_result["action"] == "approve_output"

    third = service.start(workflow_run_id=workflow_id)
    assert third["next_action"] == "continue_p3_delivery"
    assert third["current_step"]["name"] == "step_plan"


def test_demo_stops_before_delivery_controls(database) -> None:
    workflow_id = create_workflow(database)
    service = P4DemoFlowService(database)
    service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-editor")
    service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")

    result = service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")

    assert result["ok"] is False
    assert result["kind"] == "demo_approval"
    assert result["next_action"] == "continue_p3_delivery"
