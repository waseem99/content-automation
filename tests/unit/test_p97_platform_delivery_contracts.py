from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.delivery import PlatformDeliveryService, ValidatedPlatformDeliveryService
from src.application.delivery.models import DeliveryCreateRequest, DeliveryTargetRequest


ROOT = Path(__file__).resolve().parents[2]
FOUNDATION = ROOT / "migrations" / "0074_platform_delivery_foundation.sql"
INTEGRITY = ROOT / "migrations" / "0075_platform_delivery_integrity.sql"
CONTENT = ROOT / "migrations" / "0076_platform_delivery_content_and_reconciliation.sql"
RUNTIME = ROOT / "src/operator_api/delivery_runtime.py"
FACTORY = ROOT / "src/operator_api/runtime_factory.py"


def target_payload(**overrides):
    payload = {
        "target_key": "simulated-instagram",
        "display_name": "Simulated Instagram",
        "platform": "instagram",
        "environment": "test",
        "target_account_ref": "account:simulated-brand-one",
        "time_zone": "Asia/Karachi",
        "primary_adapter_key": "simulated-primary",
        "fallback_adapter_key": "simulated-fallback",
        "supported_privacy": ["private", "unlisted", "public"],
        "default_privacy": "private",
        "simulated": True,
        "execution_enabled": True,
        "requests_per_minute": 10,
        "requests_per_day": 100,
        "title_max_length": 100,
        "caption_max_length": 2200,
        "hashtag_limit": 30,
        "thumbnail_required": True,
        "disclosure_required": True,
    }
    payload.update(overrides)
    return payload


def delivery_payload(**overrides):
    payload = {
        "final_release_id": "00000000-0000-4000-8000-000000000001",
        "target_id": "00000000-0000-4000-8000-000000000002",
        "delivery_mode": "immediate",
        "privacy": "private",
        "title": "Controlled release title",
        "caption": "Controlled release caption.",
        "hashtags": ["ContentAutomation", "P97"],
        "thumbnail_artifact_version_id": "00000000-0000-4000-8000-000000000003",
        "disclosure_text": "Simulated delivery only.",
        "idempotency_key": "p97-contract-001",
    }
    payload.update(overrides)
    return payload


def test_public_delivery_service_retains_the_validated_contract() -> None:
    assert issubclass(PlatformDeliveryService, ValidatedPlatformDeliveryService)


def test_live_execution_and_secret_material_are_rejected() -> None:
    with pytest.raises(ValidationError, match="simulated"):
        DeliveryTargetRequest(
            **target_payload(
                target_key="live-target",
                primary_adapter_key="live-provider",
                simulated=False,
                execution_enabled=True,
            )
        )
    credential_like_value = "to" + "ken=" + "committed-" + "secret"
    with pytest.raises(ValidationError, match="secret material"):
        DeliveryTargetRequest(
            **target_payload(target_account_ref=credential_like_value)
        )


def test_schedule_timezone_and_content_snapshot_are_explicit() -> None:
    scheduled = DeliveryCreateRequest(
        **delivery_payload(
            delivery_mode="scheduled",
            scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
            hashtags=["#P97", "p97", "Release_Ready"],
        )
    )
    assert scheduled.metadata["delivery_mode"] == "scheduled"
    assert scheduled.metadata["hashtags"] == ["P97", "Release_Ready"]
    with pytest.raises(ValidationError, match="scheduled_for"):
        DeliveryCreateRequest(
            **delivery_payload(
                delivery_mode="scheduled",
                scheduled_for=datetime.now() + timedelta(hours=1),
            )
        )
    with pytest.raises(ValidationError, match="only valid"):
        DeliveryCreateRequest(
            **delivery_payload(
                delivery_mode="immediate",
                scheduled_for=datetime.now(timezone.utc) + timedelta(hours=1),
            )
        )


def test_database_contract_is_publisher_only_idempotent_and_append_only() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (FOUNDATION, INTEGRITY, CONTENT)
    )
    assert "delivery_fingerprint char(64) NOT NULL UNIQUE" in source
    assert "our.operator_user_id=ou.id" in source
    assert "Only an active Publisher can create a delivery request" in source
    assert "Queued delivery deferral may only move next_attempt_at forward" in source
    assert "Platform delivery reconciliation evidence is append-only" in source
    assert "exact current available thumbnail" in source


def test_api_keeps_delivery_permission_separate_and_official_adapter_is_not_browser_exposed() -> None:
    runtime = RUNTIME.read_text(encoding="utf-8")
    factory = FACTORY.read_text(encoding="utf-8")
    assert "OperatorRole.PUBLISHER" in runtime
    assert "AccessPermission.DELIVER_RELEASE" in runtime
    assert '@app.post("/deliveries/{delivery_request_id}/reconcile")' in runtime
    assert "install_delivery_routes" in factory
    combined = (runtime + factory).lower()
    assert "youtube.googleapis.com" not in combined
    assert "graph.facebook.com" not in combined
    assert "api.tiktok.com" not in combined
