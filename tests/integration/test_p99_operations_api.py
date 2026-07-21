from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from src.operations.settings import OperationsSettings
from tests.integration.test_p87_generation_jobs import database, seeded


__all__ = ["database", "seeded"]
pytestmark = pytest.mark.integration


def operations_client(database, ready) -> TestClient:
    identities = {
        str(ready["admin"]): OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Operations Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            active=True,
        ),
        str(ready["producer"]): OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Operations Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({str(ready["brand_id"])}),
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
    return TestClient(
        create_configured_app(
            database=database,
            auth_settings=auth,
            runtime_settings=OperatorRuntimeSettings(
                _env_file=None,
                database_require_schema=False,
            ),
            operations_settings=OperationsSettings(
                _env_file=None,
                environment="staging",
                release_key="staging-api-test",
                git_sha="1" * 40,
                image_digest="sha256:" + "2" * 64,
                configuration_digest="3" * 64,
                migration_head="0082_production_operations_integrity.sql",
                requests_per_minute=1000,
                storage_capacity_bytes=1024 * 1024,
            ),
        )
    )


def test_operations_api_is_admin_only_and_exposes_release_identity(database, seeded) -> None:
    client = operations_client(database, seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}

    denied = client.get("/operations/config", headers=producer)
    assert denied.status_code == 403

    configured = client.get("/operations/config", headers=admin)
    assert configured.status_code == 200, configured.text
    assert configured.json()["operations"]["release_key"] == "staging-api-test"

    runtime = client.get("/runtime/config")
    assert runtime.status_code == 200
    assert runtime.json()["operations"]["git_sha"] == "1" * 40
    assert runtime.headers["X-Request-ID"]

    payload = {
        "environment": "staging",
        "release_key": "staging-api-release-0001",
        "git_sha": "4" * 40,
        "image_digest": "sha256:" + "5" * 64,
        "configuration_digest": "6" * 64,
        "migration_head": "0082_production_operations_integrity.sql",
    }
    assert client.post("/operations/releases", headers=producer, json=payload).status_code == 403
    created = client.post("/operations/releases", headers=admin, json=payload)
    assert created.status_code == 200, created.text
    release_id = created.json()["release"]["id"]

    deploying = client.post(
        f"/operations/releases/{release_id}/transition/deploying",
        headers=admin,
    )
    assert deploying.status_code == 200, deploying.text
    healthy = client.post(
        f"/operations/releases/{release_id}/transition/healthy",
        headers=admin,
    )
    assert healthy.status_code == 200, healthy.text
    assert healthy.json()["release"]["status"] == "healthy"


def test_operations_monitor_and_alert_routes_are_admin_scoped(database, seeded) -> None:
    client = operations_client(database, seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}

    assert client.post(
        "/operations/monitor/check?environment=staging",
        headers=producer,
    ).status_code == 403
    checked = client.post(
        "/operations/monitor/check?environment=staging",
        headers=admin,
    )
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["snapshot"]["environment"] == "staging"
    assert "queue" in body["snapshot"]
    assert "storage" in body["snapshot"]

    listed = client.get("/operations/alerts?environment=staging", headers=admin)
    assert listed.status_code == 200, listed.text
    assert isinstance(listed.json()["items"], list)
    assert client.get("/operations/alerts", headers=producer).status_code == 403
