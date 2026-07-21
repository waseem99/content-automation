from fastapi.testclient import TestClient
import pytest

from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def renderer_client(database, ready) -> TestClient:
    brand_one = str(ready["brand_one"])
    identities = {
        ready["admin"]: OperatorIdentity(
            operator_id=str(ready["admin"]),
            key_name="admin-key",
            display_name="Admin One",
            roles=frozenset({OperatorRole.ADMIN}),
            active=True,
        ),
        ready["producer"]: OperatorIdentity(
            operator_id=str(ready["producer"]),
            key_name="producer-key",
            display_name="Producer One",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        ready["reviewer"]: OperatorIdentity(
            operator_id=str(ready["reviewer"]),
            key_name="reviewer-key",
            display_name="Reviewer One",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(ready["admin"]),
            "producer-key": str(ready["producer"]),
            "reviewer-key": str(ready["reviewer"]),
        },
        identities=identities,
    )
    runtime = OperatorRuntimeSettings(_env_file=None, database_require_schema=False)
    return TestClient(
        create_configured_app(database=database, auth_settings=auth, runtime_settings=runtime)
    )


def renderer_payload() -> dict:
    return {
        "renderer_key": "simulated-api",
        "display_name": "Simulated API Renderer",
        "adapter_key": "simulated",
        "operation": "image_to_video",
        "output_formats": ["mp4"],
        "min_duration_seconds": 2,
        "max_duration_seconds": 12,
        "max_width": 1080,
        "max_height": 1920,
        "capabilities": ["camera_motion"],
        "expected_seconds_base": 20,
        "expected_seconds_per_second": 4,
        "base_cost_usd": 0.25,
        "cost_per_second_usd": 0.1,
        "usage_evidence": {"sample_count": 3},
        "health": "healthy",
        "quality_rating": 4.2,
        "simulated": True,
        "execution_enabled": True,
        "configuration": {"simulation_behavior": "success"},
    }


def request_payload() -> dict:
    return {
        "operation": "image_to_video",
        "output_format": "mp4",
        "duration_seconds": 8,
        "width": 1080,
        "height": 1920,
        "required_capabilities": ["camera_motion"],
    }


def test_renderer_api_is_admin_configured_and_producer_executed(p89_database, p89_seeded) -> None:
    client = renderer_client(p89_database, p89_seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}

    denied_create = client.post("/production/renderers", headers=producer, json=renderer_payload())
    assert denied_create.status_code == 403

    created = client.post("/production/renderers", headers=admin, json=renderer_payload())
    assert created.status_code == 200, created.text
    renderer_id = created.json()["renderer"]["id"]

    activated = client.post(f"/production/renderers/{renderer_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text

    assert client.get("/production/renderers", headers=reviewer).status_code == 200
    assert client.post("/production/renderers/resolve", headers=reviewer, json=request_payload()).status_code == 403

    resolved = client.post("/production/renderers/resolve", headers=producer, json=request_payload())
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["renderer"]["id"] == renderer_id

    simulated = client.post(
        "/production/renderers/simulate",
        headers=producer,
        json={
            "renderer_id": renderer_id,
            "idempotency_key": "p93-api-simulation-001",
            "request": request_payload(),
            "input_payload": {"source_asset_id": "asset-api"},
        },
    )
    assert simulated.status_code == 200, simulated.text
    attempt_id = simulated.json()["attempt"]["id"]
    assert simulated.json()["attempt"]["status"] == "succeeded"

    attempt = client.get(f"/production/renderers/attempts/{attempt_id}", headers=producer)
    assert attempt.status_code == 200
    assert attempt.json()["attempt"]["catalogue_snapshot"]["renderer_key"] == "simulated-api"


def test_renderer_api_blocks_unsupported_request_before_attempt(p89_database, p89_seeded) -> None:
    client = renderer_client(p89_database, p89_seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    created = client.post("/production/renderers", headers=admin, json=renderer_payload())
    renderer_id = created.json()["renderer"]["id"]
    client.post(f"/production/renderers/{renderer_id}/activate", headers=admin)

    unsupported = request_payload()
    unsupported["duration_seconds"] = 30
    response = client.post(
        "/production/renderers/simulate",
        headers=producer,
        json={
            "renderer_id": renderer_id,
            "idempotency_key": "p93-api-blocked-001",
            "request": unsupported,
            "input_payload": {"source_asset_id": "asset-api"},
        },
    )
    assert response.status_code == 422
    assert "duration_not_supported" in response.json()["detail"]["reasons"]
    with p89_database.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS count FROM football_brief.production_renderer_attempts WHERE idempotency_key=%s",
            ("p93-api-blocked-001",),
        ).fetchone()["count"]
    assert count == 0
