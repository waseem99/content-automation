from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from src.application.acceptance.validated_service import p100_runbook_sha256
from src.operations.settings import OperationsSettings
from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded


__all__ = ["p89_database", "p89_seeded"]
pytestmark = pytest.mark.integration


def acceptance_client(database, ready) -> TestClient:
    identities = {
        str(ready["admin"]): OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Acceptance Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            active=True,
        ),
        str(ready["producer"]): OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Acceptance Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(ready["brand_one"])}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(ready["admin"]),
            "producer-key": str(ready["producer"]),
        },
        identities=identities,
    )
    app = create_configured_app(
        database=database,
        auth_settings=auth,
        runtime_settings=OperatorRuntimeSettings(
            _env_file=None,
            database_require_schema=False,
        ),
        operations_settings=OperationsSettings(
            _env_file=None,
            environment="staging",
            release_key="p100-configured-app-test",
            git_sha="1" * 40,
            image_digest="sha256:" + "2" * 64,
            configuration_digest="3" * 64,
            migration_head="0089_acceptance_runbook_drill.sql",
            requests_per_minute=1000,
            storage_capacity_bytes=1024 * 1024,
        ),
    )
    return TestClient(app)


def test_configured_app_installs_acceptance_routes_and_keeps_live_execution_absent(
    p89_database,
    p89_seeded,
) -> None:
    client = acceptance_client(p89_database, p89_seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}

    registered_paths = {route.path for route in client.app.routes}
    assert "/acceptance/pilots" in registered_paths
    assert "/acceptance/pilots/{pilot_id}/accept" in registered_paths
    assert "/acceptance/pilots/{pilot_id}/readiness" in registered_paths
    assert "/acceptance/pilots/{pilot_id}/live-delivery-evidence" in registered_paths
    assert not any(
        "execute-live" in path or "submit-live" in path
        for path in registered_paths
    )

    payload = {
        "pilot_key": "p100-configured-app",
        "acceptance_policy": {
            "critical_defects_allowed": 0,
            "major_defects_allowed": 0,
        },
    }
    denied = client.post("/acceptance/pilots", headers=producer, json=payload)
    assert denied.status_code == 403

    created = client.post("/acceptance/pilots", headers=admin, json=payload)
    assert created.status_code == 200, created.text
    pilot = created.json()["pilot"]
    assert pilot["status"] == "draft"
    assert pilot["scope"]["total_items"] == 4

    missing_body = client.post(f"/acceptance/pilots/{pilot['id']}/accept", headers=admin)
    assert missing_body.status_code == 422

    malformed = client.post(
        f"/acceptance/pilots/{pilot['id']}/accept",
        headers=admin,
        json={"production_release_tag": "release-1", "runbook_sha256": "bad"},
    )
    assert malformed.status_code == 422

    accept_payload = {
        "production_release_tag": "prod-p100-configured-app-01",
        "runbook_sha256": p100_runbook_sha256(),
    }
    denied_accept = client.post(
        f"/acceptance/pilots/{pilot['id']}/accept",
        headers=producer,
        json=accept_payload,
    )
    assert denied_accept.status_code == 403

    started = client.post(f"/acceptance/pilots/{pilot['id']}/start", headers=admin)
    assert started.status_code == 200, started.text
    assert started.json()["pilot"]["status"] == "running"

    premature_accept = client.post(
        f"/acceptance/pilots/{pilot['id']}/accept",
        headers=admin,
        json=accept_payload,
    )
    assert premature_accept.status_code == 422
    detail = premature_accept.json()["detail"]
    assert detail["code"] == "pilot_not_ready_for_acceptance"
    assert any(blocker["code"] == "pilot_scope_incomplete" for blocker in detail["blockers"])

    nonexistent_execution = client.post(
        f"/acceptance/pilots/{uuid4()}/execute-live-delivery",
        headers=admin,
        json={},
    )
    assert nonexistent_execution.status_code == 404
