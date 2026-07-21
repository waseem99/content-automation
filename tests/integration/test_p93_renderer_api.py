from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from src.application.renderers.models import RendererEntryRequest
from src.operator_api.access import OperatorIdentity, OperatorRole
from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app
from tests.integration.p93_renderer_support import (
    p93_database,
    p93_seeded,
    simulated_entry_request,
)


pytestmark = pytest.mark.integration


def renderer_client(database, seeded) -> TestClient:
    brand_one = str(seeded["brand_one"])
    brand_two = str(seeded["brand_two"])
    identities = {
        seeded["admin"]: OperatorIdentity(
            operator_id=str(seeded["admin"]),
            key_name="admin-key",
            display_name="Renderer Admin",
            roles=frozenset({OperatorRole.ADMIN}),
            brand_ids=frozenset(),
            active=True,
        ),
        seeded["producer"]: OperatorIdentity(
            operator_id=str(seeded["producer"]),
            key_name="producer-key",
            display_name="Renderer Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        seeded["reviewer"]: OperatorIdentity(
            operator_id=str(seeded["reviewer"]),
            key_name="reviewer-key",
            display_name="Renderer Reviewer",
            roles=frozenset({OperatorRole.REVIEWER}),
            brand_ids=frozenset({brand_one}),
            active=True,
        ),
        seeded["outsider"]: OperatorIdentity(
            operator_id=str(seeded["outsider"]),
            key_name="outsider-key",
            display_name="Other Producer",
            roles=frozenset({OperatorRole.PRODUCER}),
            brand_ids=frozenset({brand_two}),
            active=True,
        ),
    }
    auth = OperatorAuthSettings(
        api_keys={
            "admin-key": str(seeded["admin"]),
            "producer-key": str(seeded["producer"]),
            "reviewer-key": str(seeded["reviewer"]),
            "outsider-key": str(seeded["outsider"]),
        },
        identities=identities,
    )
    runtime = OperatorRuntimeSettings(_env_file=None, database_require_schema=False)
    return TestClient(
        create_configured_app(
            database=database,
            auth_settings=auth,
            runtime_settings=runtime,
        )
    )


def preflight_payload(seeded, *, content_key="content_one", version_key="content_one_version") -> dict:
    return {
        "portfolio_content_id": str(seeded[content_key]),
        "content_version": int(seeded[version_key]),
        "operation": "image_to_video",
        "format": "vertical_9_16",
        "duration_seconds": "5",
        "width": 704,
        "height": 1280,
        "fps": 24,
        "required_capabilities": ["camera_control", "character_consistency"],
        "input_asset_ids": [],
        "request_metadata": {"shot_id": "S01", "source": "p93-api-test"},
    }


def managed_entry_request() -> RendererEntryRequest:
    return RendererEntryRequest(
        provider_key="managed-test",
        provider_display_name="Managed Test Renderer",
        model_key="managed-video-v1",
        model_display_name="Managed Video v1",
        operation="image_to_video",
        adapter_kind="http_api",
        supported_formats=("vertical_9_16",),
        min_duration_seconds=Decimal("2"),
        max_duration_seconds=Decimal("10"),
        duration_step_seconds=Decimal("1"),
        supported_resolutions=({"width": 704, "height": 1280},),
        capabilities={"camera_control": True, "character_consistency": True},
        expected_latency_seconds={"p50": 30, "p95": 90},
        pricing={"base_usd": "1", "per_second_usd": "0.2"},
        pricing_currency="USD",
        quality_rating=Decimal("88"),
        commercial_use_allowed=True,
        usage_terms_url="https://example.test/managed-terms",
        usage_evidence_digest="e" * 64,
        usage_evidence_recorded_at=datetime.now(timezone.utc),
        data_handling={"retention_days": 7, "training_use": False},
        notes="Test-only catalogue entry. No provider credential is configured.",
    )


def test_renderer_api_enforces_admin_mutations_and_brand_scoped_preflight(
    p93_database,
    p93_seeded,
) -> None:
    client = renderer_client(p93_database, p93_seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}
    reviewer = {"X-Operator-Key": "reviewer-key"}
    outsider = {"X-Operator-Key": "outsider-key"}
    entry_payload = simulated_entry_request().model_dump(mode="json")

    assert client.post("/renderers/catalogue", headers=producer, json=entry_payload).status_code == 403
    assert client.post("/renderers/catalogue", headers=reviewer, json=entry_payload).status_code == 403

    created = client.post("/renderers/catalogue", headers=admin, json=entry_payload)
    assert created.status_code == 200, created.text
    entry_id = created.json()["entry"]["id"]

    producer_activate = client.post(f"/renderers/catalogue/{entry_id}/activate", headers=producer)
    assert producer_activate.status_code == 403
    activated = client.post(f"/renderers/catalogue/{entry_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text
    assert activated.json()["entry"]["status"] == "active"

    for headers in (admin, producer, reviewer, outsider):
        listed = client.get("/renderers/catalogue?status=active", headers=headers)
        assert listed.status_code == 200, listed.text
        assert any(item["id"] == entry_id for item in listed.json()["entries"])

    reviewer_preflight = client.post(
        "/renderers/preflight",
        headers=reviewer,
        json=preflight_payload(p93_seeded),
    )
    assert reviewer_preflight.status_code == 403

    outsider_preflight = client.post(
        "/renderers/preflight",
        headers=outsider,
        json=preflight_payload(p93_seeded),
    )
    assert outsider_preflight.status_code == 403

    own_preflight = client.post(
        "/renderers/preflight",
        headers=producer,
        json=preflight_payload(p93_seeded),
    )
    assert own_preflight.status_code == 200, own_preflight.text
    preflight = own_preflight.json()["preflight"]
    assert preflight["accepted"] is True
    assert preflight["renderer_catalogue_entry_id"] == entry_id
    assert float(preflight["estimated_cost"]) == 0
    assert preflight["external_fee_possible"] is False

    enqueued = client.post(
        "/renderers/simulated-jobs",
        headers=producer,
        json={"renderer_preflight_id": preflight["id"], "max_attempts": 1},
    )
    assert enqueued.status_code == 200, enqueued.text
    assert enqueued.json()["job"]["provider"] == "simulated"
    assert enqueued.json()["job"]["job_type"] == "premium_clip"
    assert float(enqueued.json()["job"]["estimated_cost_usd"]) == 0


def test_renderer_api_records_unsupported_request_and_blocks_paid_execution(
    p93_database,
    p93_seeded,
) -> None:
    client = renderer_client(p93_database, p93_seeded)
    admin = {"X-Operator-Key": "admin-key"}
    producer = {"X-Operator-Key": "producer-key"}

    managed = client.post(
        "/renderers/catalogue",
        headers=admin,
        json=managed_entry_request().model_dump(mode="json"),
    )
    assert managed.status_code == 200, managed.text
    managed_id = managed.json()["entry"]["id"]
    health = client.post(
        f"/renderers/catalogue/{managed_id}/health",
        headers=admin,
        json={
            "status": "healthy",
            "latency_ms": 1200,
            "checked_by": "p93-api-test",
            "details": {"simulated_observation": True},
        },
    )
    assert health.status_code == 200, health.text
    activated = client.post(f"/renderers/catalogue/{managed_id}/activate", headers=admin)
    assert activated.status_code == 200, activated.text

    paid_payload = preflight_payload(p93_seeded)
    paid_payload["renderer_catalogue_entry_id"] = managed_id
    paid_preflight_response = client.post(
        "/renderers/preflight",
        headers=producer,
        json=paid_payload,
    )
    assert paid_preflight_response.status_code == 200, paid_preflight_response.text
    paid_preflight = paid_preflight_response.json()["preflight"]
    assert paid_preflight["accepted"] is True
    assert float(paid_preflight["estimated_cost"]) == 2.0
    assert paid_preflight["external_fee_possible"] is True

    paid_enqueue = client.post(
        "/renderers/simulated-jobs",
        headers=producer,
        json={"renderer_preflight_id": paid_preflight["id"]},
    )
    assert paid_enqueue.status_code == 403
    assert paid_enqueue.json()["detail"]["code"] == "paid_renderer_execution_disabled"

    unsupported_payload = preflight_payload(p93_seeded)
    unsupported_payload.update({"format": "horizontal_16_9", "duration_seconds": "30"})
    unsupported_response = client.post(
        "/renderers/preflight",
        headers=producer,
        json=unsupported_payload,
    )
    assert unsupported_response.status_code == 200, unsupported_response.text
    unsupported = unsupported_response.json()["preflight"]
    assert unsupported["accepted"] is False
    assert "unsupported_format" in unsupported["rejection_reasons"]
    assert "unsupported_duration" in unsupported["rejection_reasons"]

    rejected_enqueue = client.post(
        "/renderers/simulated-jobs",
        headers=producer,
        json={"renderer_preflight_id": unsupported["id"]},
    )
    assert rejected_enqueue.status_code == 422
    assert rejected_enqueue.json()["detail"]["code"] == "renderer_preflight_rejected"
