from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.operator_api import create_app
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def test_health_route_without_database() -> None:
    payload = TestClient(create_app()).get("/health").json()

    assert payload["ok"] is True
    assert payload["database_configured"] is False


def test_demo_and_dashboard_routes(database) -> None:
    workflow_id = create_workflow(database)
    client = TestClient(create_app(database))

    assert client.get("/health").json()["database_configured"] is True
    assert client.get("/demo/scenario").json()["kind"] == "demo_scenario"

    started = client.post(f"/demo/{workflow_id}/start").json()
    assert started["next_action"] == "approve_packet"

    cards = client.get(f"/workflows/{workflow_id}/dashboard/queue").json()
    assert cards["kind"] == "queue_cards"
    assert cards["cards"][0]["item_type"] == "packet_review"

    schema = client.get(f"/workflows/{workflow_id}/dashboard/schema").json()
    assert schema["kind"] == "dashboard_schema"
    assert schema["workflow_run_id"] == str(workflow_id)


def test_workflow_approval_and_audit_routes(database) -> None:
    workflow_id = create_workflow(database)
    client = TestClient(create_app(database))

    run = client.post(
        f"/workflows/{workflow_id}/run",
        json={"topic": "Football match preview demo", "source_urls": ["https://example.com/p5/source"], "actor": "api-test"},
    ).json()
    assert run["next_action"] == "approve_packet"

    item = client.get(f"/workflows/{workflow_id}/queue").json()["items"][0]
    approval = client.post(
        f"/workflows/{workflow_id}/approvals",
        json={"action": "approve_packet", "resource_id": item["id"], "reviewed_by": "api-editor"},
    ).json()
    assert approval["status"] == "approved"

    audit = client.get(f"/workflows/{workflow_id}/audit").json()
    assert audit["kind"] == "audit_report"
    assert audit["status"]["review_count"] >= 1
