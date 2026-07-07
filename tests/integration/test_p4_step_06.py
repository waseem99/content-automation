from __future__ import annotations

import pytest

from src.application.p4_audit import P4AuditReportService
from src.application.p4_dashboard import P4DashboardContracts
from src.application.p4_demo_flow import P4DemoFlowService
from src.application.p4_surface import P4OperatorSurface
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_p4_closeout_pilot_services_compose(database) -> None:
    workflow_id = create_workflow(database)
    demo = P4DemoFlowService(database)
    dashboard = P4DashboardContracts(database)
    surface = P4OperatorSurface(database)
    audit = P4AuditReportService(database)

    first_state = demo.start(workflow_run_id=workflow_id)
    assert first_state["ok"] is True
    assert first_state["next_action"] == "approve_packet"

    first_queue = dashboard.queue_cards(workflow_run_id=workflow_id)
    assert first_queue["ok"] is True
    assert first_queue["cards"][0]["actions"][0]["name"] == "approve_packet"

    packet_result = demo.approve_current(workflow_run_id=workflow_id, reviewed_by="closeout-editor")
    assert packet_result["ok"] is True
    assert packet_result["status"] == "approved"

    second_state = demo.start(workflow_run_id=workflow_id)
    assert second_state["next_action"] == "approve_output"
    second_queue = surface.queue(workflow_run_id=workflow_id)
    assert second_queue["ok"] is True
    assert second_queue["items"][0]["type"] == "source_output_review"

    output_result = demo.approve_current(workflow_run_id=workflow_id, reviewed_by="closeout-producer")
    assert output_result["ok"] is True
    assert output_result["status"] == "approved"

    final_state = demo.start(workflow_run_id=workflow_id)
    assert final_state["ok"] is True
    assert final_state["next_action"] == "continue_p3_delivery"
    assert final_state["current_step"]["name"] == "step_plan"

    report = audit.report(workflow_run_id=workflow_id)
    assert report["ok"] is True
    assert report["status"]["event_count"] >= 1
    assert report["status"]["review_count"] >= 2
    assert any(review["review_type"] == "packet_review" and review["status"] == "approved" for review in report["reviews"])
    assert any(review["review_type"] == "source_output_review" and review["status"] == "approved" for review in report["reviews"])
