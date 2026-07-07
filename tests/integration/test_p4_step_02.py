from __future__ import annotations

import pytest

from src.application.p3_step_five import P3DeliveryManifestService
from src.application.p4_surface import P4OperatorSurface
from tests.integration.rights_support import close_database, create_workflow, database_fixture
from tests.integration.test_p3_step_04 import _package


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _topic_payload():
    return {"topic": "Derby preview", "source_urls": ("https://example.com/story",), "actor": "pytest"}


def test_surface_creates_intake_runs_workflow_and_lists_queue(database) -> None:
    workflow_id = create_workflow(database)
    surface = P4OperatorSurface(database)

    created = surface.create_intake(workflow_run_id=workflow_id, **_topic_payload())
    assert created["ok"] is True
    assert created["kind"] == "intake_create"
    assert created["workflow_run_id"] == str(workflow_id)
    assert created["reference_count"] == 1

    run = surface.run_workflow(workflow_run_id=workflow_id, **_topic_payload())
    assert run["ok"] is True
    assert run["kind"] == "workflow_run"
    assert run["status"] == "waiting"
    assert run["next_action"] == "approve_packet"
    assert run["steps"][-1]["name"] == "packet_review"

    queue = surface.queue(workflow_run_id=workflow_id)
    assert queue["ok"] is True
    assert queue["kind"] == "queue"
    assert queue["workflow_run_id"] == str(workflow_id)
    assert queue["items"][0]["type"] == "packet_review"
    assert queue["items"][0]["status"] == "pending"


def test_surface_approval_actions_resume_control_path(database) -> None:
    workflow_id = create_workflow(database)
    surface = P4OperatorSurface(database)
    first = surface.run_workflow(workflow_run_id=workflow_id, **_topic_payload())
    packet_id = first["steps"][1]["resource_id"]

    approved_packet = surface.approve_packet(workflow_run_id=workflow_id, packet_id=packet_id, reviewed_by="editor")
    assert approved_packet["ok"] is True
    assert approved_packet["kind"] == "approve_packet"
    assert approved_packet["status"] == "approved"

    second = surface.run_workflow(workflow_run_id=workflow_id, **_topic_payload())
    assert second["next_action"] == "approve_output"
    output_id = second["steps"][3]["resource_id"]

    approved_output = surface.approve_output(workflow_run_id=workflow_id, source_output_id=output_id, reviewed_by="producer")
    assert approved_output["ok"] is True
    assert approved_output["kind"] == "approve_output"
    assert approved_output["status"] == "approved"

    third = surface.run_workflow(workflow_run_id=workflow_id, **_topic_payload())
    assert third["ok"] is True
    assert third["status"] == "waiting"
    assert third["next_action"] == "continue_p3_delivery"
    assert third["steps"][-1]["name"] == "step_plan"


def test_surface_package_and_manifest_contracts(database) -> None:
    workflow_id, package = _package(database)
    surface = P4OperatorSurface(database)

    package_status = surface.package_status(workflow_run_id=workflow_id, package_id=package.id)
    assert package_status["ok"] is True
    assert package_status["kind"] == "package_status"
    assert package_status["id"] == str(package.id)
    assert package_status["review_status"] == "missing"

    requested = surface.request_package(workflow_run_id=workflow_id, package_id=package.id)
    assert requested["ok"] is True
    assert requested["status"] == "pending"

    approved = surface.approve_package(workflow_run_id=workflow_id, package_id=package.id, reviewed_by="producer")
    assert approved["ok"] is True
    assert approved["status"] == "approved"

    manifest = P3DeliveryManifestService(database).create_for_package(workflow_run_id=workflow_id, package_id=package.id, actor="pytest").manifest
    assert manifest is not None
    manifest_status = surface.manifest_status(workflow_run_id=workflow_id, package_id=package.id)
    assert manifest_status["ok"] is True
    assert manifest_status["kind"] == "manifest_status"
    assert manifest_status["items"][0]["id"] == str(manifest.id)
    assert manifest_status["items"][0]["package_id"] == str(package.id)


def test_surface_invalid_resource_ids_fail_closed(database) -> None:
    workflow_id, package = _package(database)
    other_workflow_id = create_workflow(database)
    surface = P4OperatorSurface(database)

    wrong_workflow = surface.approve_package(workflow_run_id=other_workflow_id, package_id=package.id, reviewed_by="producer")
    assert wrong_workflow["ok"] is False
    assert wrong_workflow["kind"] == "approve_package"
    assert "package" in wrong_workflow["error"]

    package_status = surface.package_status(workflow_run_id=workflow_id, package_id=package.id)
    assert package_status["ok"] is True
    assert package_status["review_status"] == "missing"
