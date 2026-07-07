from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.rights_support import close_database, create_workflow, database_fixture
from tests.integration.test_p3_step_04 import _package


pytestmark = pytest.mark.integration


KEY = "contract-key"
HEADERS = {"X-Operator-Key": KEY}


@pytest.fixture()
def database():
    value = database_fixture()
    try:
        yield value
    finally:
        close_database(value)


def _client(database=None) -> TestClient:
    return TestClient(create_configured_app(database, auth_settings=OperatorAuthSettings.for_tests(key=KEY, operator_id="contract-operator")))


def test_health_and_runtime_contracts_are_stable() -> None:
    client = _client()

    health = client.get("/health").json()
    runtime = client.get("/runtime/config").json()

    assert {"ok", "service", "version", "database_configured", "auth_required"}.issubset(health)
    assert health["ok"] is True
    assert health["auth_required"] is True
    assert runtime["ok"] is True
    assert runtime["kind"] == "runtime_config"
    assert {"api_host", "api_port", "log_level", "demo_mode", "database_require_schema", "database_migrations_dir"}.issubset(runtime["runtime"])


def test_queue_dashboard_and_schema_contracts_are_stable(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)
    client.post(f"/demo/{workflow_id}/start", headers=HEADERS)

    queue = client.get(f"/workflows/{workflow_id}/queue", headers=HEADERS).json()
    cards = client.get(f"/workflows/{workflow_id}/dashboard/queue", headers=HEADERS).json()
    schema = client.get(f"/workflows/{workflow_id}/dashboard/schema", headers=HEADERS).json()

    assert queue["ok"] is True
    assert queue["operator"] == "contract-operator"
    assert {"workflow_run_id", "items"}.issubset(queue)
    assert {"type", "id", "workflow_run_id", "status", "title", "created_at", "metadata"}.issubset(queue["items"][0])

    assert cards["ok"] is True
    assert cards["kind"] == "queue_cards"
    assert cards["operator"] == "contract-operator"
    assert cards["count"] == 1
    assert {"card_id", "resource_id", "item_type", "status", "title", "subtitle", "created_at", "actions", "metadata"}.issubset(cards["cards"][0])

    assert schema["ok"] is True
    assert schema["kind"] == "dashboard_schema"
    assert "queue_card_fields" in schema
    assert "error_fields" in schema


def test_demo_workflow_approval_and_audit_contracts(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)

    scenario = client.get("/demo/scenario", headers=HEADERS).json()
    started = client.post(f"/demo/{workflow_id}/start", headers=HEADERS).json()
    status = client.get(f"/demo/{workflow_id}/status", headers=HEADERS).json()
    current = client.post(f"/demo/{workflow_id}/approve-current", headers=HEADERS, json={}).json()
    audit = client.get(f"/workflows/{workflow_id}/audit", headers=HEADERS).json()

    assert scenario["ok"] is True
    assert scenario["kind"] == "demo_scenario"
    assert "expected_stop_points" in scenario
    assert started["ok"] is True
    assert started["kind"] == "blocked_state"
    assert started["next_action"] == "approve_packet"
    assert status["ok"] is True
    assert status["kind"] == "demo_status"
    assert current["ok"] is True
    assert current["kind"] == "approval_action"
    assert current["status"] == "approved"
    assert current["reviewed_by"] == "contract-operator"
    assert audit["ok"] is True
    assert audit["kind"] == "audit_report"
    assert audit["operator"] == "contract-operator"
    assert {"workflow", "status", "timeline", "reviews", "queue", "packages", "manifests"}.issubset(audit)


def test_approval_route_fails_closed_for_wrong_workflow_resource(database) -> None:
    workflow_id, package = _package(database)
    other_workflow_id = create_workflow(database)
    client = _client(database)

    response = client.post(
        f"/workflows/{other_workflow_id}/approvals",
        headers=HEADERS,
        json={"action": "approve_package", "resource_id": str(package.id)},
    ).json()

    assert response["ok"] is False
    assert response["kind"] == "approval_action"
    assert response["action"] == "approve_package"
    assert response["resource_id"] == str(package.id)
    assert "package" in response["error"]


def test_invalid_inputs_fail_closed_at_http_boundary(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)

    invalid_workflow = client.get("/workflows/not-a-uuid/queue", headers=HEADERS)
    missing_body = client.post(f"/workflows/{workflow_id}/approvals", headers=HEADERS, json={})
    unsupported_action = client.post(
        f"/workflows/{workflow_id}/approvals",
        headers=HEADERS,
        json={"action": "auto_publish", "resource_id": str(workflow_id)},
    ).json()

    assert invalid_workflow.status_code == 422
    assert missing_body.status_code == 422
    assert unsupported_action["ok"] is False
    assert unsupported_action["kind"] == "approval_action"
    assert "unsupported" in unsupported_action["error"]


def test_protected_route_contract_requires_valid_operator_key(database) -> None:
    workflow_id = create_workflow(database)
    client = _client(database)

    missing = client.get(f"/workflows/{workflow_id}/dashboard/queue")
    invalid = client.get(f"/workflows/{workflow_id}/dashboard/queue", headers={"X-Operator-Key": "bad-key"})
    valid = client.get(f"/workflows/{workflow_id}/dashboard/queue", headers=HEADERS)

    assert missing.status_code == 401
    assert missing.json()["detail"] == "operator key is required"
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "operator key is invalid"
    assert valid.status_code == 200
    assert valid.json()["ok"] is True
