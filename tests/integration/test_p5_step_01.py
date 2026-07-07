from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_app import create_app
from tests.integration.rights_support import close_database, create_workflow, database_fixture


pytestmark = pytest.mark.integration


KEY = "test-key"
HEADERS = {"X-Operator-Key": KEY}


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _client(database=None) -> TestClient:
    return TestClient(create_app(database, auth_settings=OperatorAuthSettings.for_tests(key=KEY, operator_id="api-operator")))


def test_health_route_without_database() -> None:
    payload = TestClient(create_app()).get("/health").json()

    assert payload["ok"] is True
    assert payload["database_configured"] is False
    assert payload["auth_required"] is True


def test_protected_routes_reject_missing_and_invalid_auth(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)

    missing = client.get(f"/workflows/{workflow_id}/queue")
    assert missing.status_code == 401
    assert missing.json()["detail"] == "operator key is required"

    invalid = client.get(f"/workflows/{workflow_id}/queue", headers={"X-Operator-Key": "wrong-key"})
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "operator key is invalid"


def test_demo_and_dashboard_routes(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)

    assert client.get("/health").json()["database_configured"] is True
    scenario = client.get("/demo/scenario", headers=HEADERS).json()
    assert scenario["kind"] == "demo_scenario"
    assert scenario["operator"] == "api-operator"

    started = client.post(f"/demo/{workflow_id}/start", headers=HEADERS).json()
    assert started["next_action"] == "approve_packet"

    cards = client.get(f"/workflows/{workflow_id}/dashboard/queue", headers=HEADERS).json()
    assert cards["kind"] == "queue_cards"
    assert cards["operator"] == "api-operator"
    assert cards["cards"][0]["item_type"] == "packet_review"

    schema = client.get(f"/workflows/{workflow_id}/dashboard/schema", headers=HEADERS).json()
    assert schema["kind"] == "dashboard_schema"
    assert schema["operator"] == "api-operator"
    assert schema["workflow_run_id"] == str(workflow_id)


def test_workflow_approval_and_audit_routes_use_authenticated_operator(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)

    run = client.post(
        f"/workflows/{workflow_id}/run",
        headers=HEADERS,
        json={"topic": "Football match preview demo", "source_urls": ["https://example.com/p5/source"]},
    ).json()
    assert run["next_action"] == "approve_packet"

    queue = client.get(f"/workflows/{workflow_id}/queue", headers=HEADERS).json()
    assert queue["operator"] == "api-operator"
    item = queue["items"][0]
    approval = client.post(
        f"/workflows/{workflow_id}/approvals",
        headers=HEADERS,
        json={"action": "approve_packet", "resource_id": item["id"]},
    ).json()
    assert approval["status"] == "approved"
    assert approval["reviewed_by"] == "api-operator"

    audit = client.get(f"/workflows/{workflow_id}/audit", headers=HEADERS).json()
    assert audit["kind"] == "audit_report"
    assert audit["operator"] == "api-operator"
    assert any(review["review_type"] == "packet_review" and review["reviewed_by"] == "api-operator" for review in audit["reviews"])


def test_explicit_local_test_mode_is_disabled_only_when_requested(database) -> None:
    workflow_id = create_workflow(database)
    client = TestClient(create_app(database, auth_settings=OperatorAuthSettings.disabled_for_local_tests(operator_id="local-operator")))

    queue = client.get(f"/workflows/{workflow_id}/queue").json()

    assert queue["ok"] is True
    assert queue["operator"] == "local-operator"
