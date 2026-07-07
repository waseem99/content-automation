from __future__ import annotations

import pytest

from src.application.p3_step_five import P3DeliveryManifestService
from src.application.p4_dashboard import P4DashboardContracts
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


def test_dashboard_queue_cards_and_review_detail_contract(database) -> None:
    workflow_id = create_workflow(database)
    dashboard = P4DashboardContracts(database)
    blocked = dashboard.blocked_state(workflow_run_id=workflow_id, **_topic_payload())
    assert blocked["ok"] is True
    assert blocked["is_blocked"] is True
    assert blocked["next_action"] == "approve_packet"

    cards = dashboard.queue_cards(workflow_run_id=workflow_id)
    assert cards["ok"] is True
    assert cards["kind"] == "queue_cards"
    assert cards["count"] == 1
    card = cards["cards"][0]
    assert set(["card_id", "resource_id", "item_type", "status", "title", "subtitle", "created_at", "actions", "metadata"]).issubset(card)
    assert card["item_type"] == "packet_review"
    assert card["actions"][0]["name"] == "approve_packet"
    assert card["actions"][0]["enabled"] is True

    detail = dashboard.review_detail(workflow_run_id=workflow_id, item_type=card["item_type"], resource_id=card["resource_id"])
    assert detail["ok"] is True
    assert detail["kind"] == "review_detail"
    assert detail["card"]["card_id"] == card["card_id"]
    assert detail["actions"] == card["actions"]


def test_dashboard_approval_action_contract(database) -> None:
    workflow_id = create_workflow(database)
    dashboard = P4DashboardContracts(database)
    dashboard.blocked_state(workflow_run_id=workflow_id, **_topic_payload())
    card = dashboard.queue_cards(workflow_run_id=workflow_id)["cards"][0]

    action = dashboard.approval_action(
        action="approve_packet",
        workflow_run_id=workflow_id,
        resource_id=card["resource_id"],
        reviewed_by="editor",
        rationale="approved for draft",
    )

    assert action["ok"] is True
    assert action["kind"] == "approval_action"
    assert action["action"] == "approve_packet"
    assert action["resource_id"] == card["resource_id"]
    assert action["status"] == "approved"
    assert action["reviewed_by"] == "editor"

    unsupported = dashboard.approval_action(action="auto_publish", workflow_run_id=workflow_id, resource_id=card["resource_id"])
    assert unsupported["ok"] is False
    assert unsupported["kind"] == "approval_action"
    assert "unsupported" in unsupported["error"]


def test_dashboard_package_and_manifest_views(database) -> None:
    workflow_id, package = _package(database)
    dashboard = P4DashboardContracts(database)

    package_view = dashboard.package_view(workflow_run_id=workflow_id, package_id=package.id)
    assert package_view["ok"] is True
    assert package_view["kind"] == "package_view"
    assert package_view["package_id"] == str(package.id)
    assert package_view["status"] == "missing"

    approved = dashboard.approval_action(action="approve_package", workflow_run_id=workflow_id, resource_id=package.id, reviewed_by="producer")
    assert approved["ok"] is True
    assert approved["status"] == "approved"

    manifest = P3DeliveryManifestService(database).create_for_package(workflow_run_id=workflow_id, package_id=package.id, actor="pytest").manifest
    assert manifest is not None

    manifest_view = dashboard.manifest_view(workflow_run_id=workflow_id, package_id=package.id)
    assert manifest_view["ok"] is True
    assert manifest_view["kind"] == "manifest_view"
    assert manifest_view["count"] == 1
    assert manifest_view["items"][0]["id"] == str(manifest.id)


def test_dashboard_error_and_schema_contracts(database) -> None:
    workflow_id, package = _package(database)
    other_workflow_id = create_workflow(database)
    dashboard = P4DashboardContracts(database)

    missing = dashboard.review_detail(workflow_run_id=workflow_id, item_type="missing", resource_id=package.id)
    assert missing["ok"] is False
    assert set(["ok", "kind", "error"]).issubset(missing)

    wrong_package = dashboard.package_view(workflow_run_id=other_workflow_id, package_id=package.id)
    assert wrong_package["ok"] is False
    assert wrong_package["kind"] == "package_view"
    assert "package" in wrong_package["error"]

    schema = dashboard.schema()
    assert schema["ok"] is True
    assert schema["kind"] == "dashboard_schema"
    assert "queue_card_fields" in schema
    assert "blocked_state_fields" in schema
    assert "error_fields" in schema
