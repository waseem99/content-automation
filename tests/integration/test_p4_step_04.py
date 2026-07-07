from __future__ import annotations

import pytest

from src.application.p4_demo import P4_DEMO_SCENARIO, P4DemoService
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_demo_scenario_is_deterministic_and_network_free(database) -> None:
    scenario = P4DemoService(database).scenario()

    assert scenario["ok"] is True
    assert scenario["kind"] == "demo_scenario"
    assert scenario["scenario_id"] == "p4-demo-derby-preview"
    assert scenario["topic"] == P4_DEMO_SCENARIO.topic
    assert scenario["source_urls"] == list(P4_DEMO_SCENARIO.source_urls)
    assert all(url.startswith("https://example.com/p4-demo/") for url in scenario["source_urls"])
    assert scenario["expected_stop_points"] == ["approve_packet", "approve_output", "continue_p3_delivery"]


def test_demo_starts_at_packet_review_stop_point(database) -> None:
    workflow_id = create_workflow(database)
    service = P4DemoService(database)

    state = service.start(workflow_run_id=workflow_id)

    assert state["ok"] is True
    assert state["kind"] == "blocked_state"
    assert state["is_blocked"] is True
    assert state["next_action"] == "approve_packet"
    assert state["current_step"]["name"] == "packet_review"

    status = service.status(workflow_run_id=workflow_id)
    assert status["ok"] is True
    assert status["kind"] == "demo_status"
    assert status["queue"]["count"] == 1
    assert status["queue"]["cards"][0]["item_type"] == "packet_review"


def test_demo_can_advance_to_source_output_review_then_step_plan(database) -> None:
    workflow_id = create_workflow(database)
    service = P4DemoService(database)

    first = service.start(workflow_run_id=workflow_id)
    assert first["next_action"] == "approve_packet"
    first_approval = service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-editor")
    assert first_approval["ok"] is True
    assert first_approval["action"] == "approve_packet"
    assert first_approval["status"] == "approved"

    second = service.start(workflow_run_id=workflow_id)
    assert second["next_action"] == "approve_output"
    assert second["current_step"]["name"] == "source_output_review"
    second_approval = service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")
    assert second_approval["ok"] is True
    assert second_approval["action"] == "approve_output"
    assert second_approval["status"] == "approved"

    third = service.start(workflow_run_id=workflow_id)
    assert third["ok"] is True
    assert third["next_action"] == "continue_p3_delivery"
    assert third["current_step"]["name"] == "step_plan"
    assert third["current_step"]["status"] == "done"


def test_demo_does_not_auto_approve_unsupported_stop_points(database) -> None:
    workflow_id = create_workflow(database)
    service = P4DemoService(database)
    service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-editor")
    service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")

    unsupported = service.approve_current(workflow_run_id=workflow_id, reviewed_by="demo-producer")

    assert unsupported["ok"] is False
    assert unsupported["kind"] == "demo_approval"
    assert unsupported["next_action"] == "continue_p3_delivery"
