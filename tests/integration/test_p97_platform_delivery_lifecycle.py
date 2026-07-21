from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import src.application.delivery.service as delivery_service_module
from src.application.delivery import (
    DeliveryAdapterError,
    DeliveryAdapterResult,
    DeliveryPlatformStatus,
    DeliveryReconciliationResult,
    PlatformDeliveryError,
    PlatformDeliveryService,
)
from src.application.delivery.models import (
    DeliveryCancelRequest,
    DeliveryClaimRequest,
    DeliveryCreateRequest,
    DeliveryExecuteRequest,
    DeliveryTargetRequest,
)
from tests.integration.p97_delivery_support import p89_database, p97_ready


pytestmark = pytest.mark.integration


def target_request(*, key: str, **overrides) -> DeliveryTargetRequest:
    payload = {
        "target_key": key,
        "display_name": f"Controlled {key}",
        "platform": "instagram",
        "environment": "test",
        "target_account_ref": f"account:{key}",
        "time_zone": "Asia/Karachi",
        "primary_adapter_key": "simulated-primary",
        "fallback_adapter_key": "simulated-fallback",
        "supported_privacy": ("private", "unlisted", "public"),
        "default_privacy": "private",
        "simulated": True,
        "execution_enabled": True,
        "requests_per_minute": 20,
        "requests_per_day": 200,
        "title_max_length": 100,
        "caption_max_length": 500,
        "hashtag_limit": 5,
        "thumbnail_required": True,
        "disclosure_required": True,
        "configuration": {},
    }
    payload.update(overrides)
    return DeliveryTargetRequest(**payload)


def delivery_request(ready, target, *, key: str, privacy: str = "private", **overrides):
    payload = {
        "final_release_id": ready["release_id"],
        "target_id": target["id"],
        "delivery_mode": "immediate",
        "privacy": privacy,
        "title": "Approved release package",
        "caption": "Exact approved package delivered through the simulated P97 adapter.",
        "hashtags": ("P97", "ReleaseReady"),
        "thumbnail_artifact_version_id": ready["thumbnail"]["id"],
        "disclosure_text": "Simulated platform delivery; no live post is created.",
        "idempotency_key": key,
        "max_attempts": 3,
    }
    payload.update(overrides)
    return DeliveryCreateRequest(**payload)


def activate(service, request, *, admin):
    target = service.create_target(request, actor=admin)["target"]
    return service.activate_target(target_id=target["id"], actor=admin)["target"]


def claim(service, ready, target, *, lease_seconds: int = 180):
    return service.claim_due(
        DeliveryClaimRequest(
            worker_id=ready["publisher"],
            target_ids=(target["id"],),
            lease_seconds=lease_seconds,
        ),
        allowed_brand_ids=(ready["brand_one"],),
    )


def execute(service, ready, claimed):
    return service.execute_claim(
        DeliveryExecuteRequest(
            delivery_request_id=claimed["delivery"]["id"],
            worker_id=ready["publisher"],
            lease_token=claimed["lease_token"],
        )
    )


def test_immediate_delivery_is_idempotent_rate_limited_and_reconciled(
    p89_database,
    p97_ready,
) -> None:
    service = PlatformDeliveryService(p89_database)
    target = activate(
        service,
        target_request(key="simulated-primary-target", requests_per_minute=1),
        admin=p97_ready["admin"],
    )
    request = delivery_request(p97_ready, target, key="p97-primary-001")
    created = service.create_delivery(request, actor=p97_ready["publisher"])
    reused = service.create_delivery(request, actor=p97_ready["publisher"])
    duplicate = service.create_delivery(
        request.model_copy(update={"idempotency_key": "p97-primary-duplicate"}),
        actor=p97_ready["publisher"],
    )
    assert created["reused"] is False
    assert reused["reused"] is True
    assert duplicate["duplicate_prevented"] is True
    assert duplicate["delivery"]["id"] == created["delivery"]["id"]

    claimed = claim(service, p97_ready, target)
    assert claimed is not None
    succeeded = execute(service, p97_ready, claimed)
    assert succeeded["delivery"]["status"] == "succeeded"
    assert succeeded["delivery"]["platform_reference"].startswith("simulated://")
    repeated = execute(service, p97_ready, claimed)
    assert repeated["reused"] is True
    detail = service.detail(delivery_request_id=created["delivery"]["id"])
    assert len(detail["attempts"]) == 1

    first_reconciliation = service.reconcile_delivery(
        delivery_request_id=created["delivery"]["id"],
        actor=p97_ready["publisher"],
    )
    second_reconciliation = service.reconcile_delivery(
        delivery_request_id=created["delivery"]["id"],
        actor=p97_ready["publisher"],
    )
    assert first_reconciliation["reconciliation"]["platform_status"] == "published"
    assert second_reconciliation["reconciliation"]["sequence_number"] == 2
    assert len(service.detail(delivery_request_id=created["delivery"]["id"])["reconciliations"]) == 2

    public_delivery = service.create_delivery(
        delivery_request(
            p97_ready,
            target,
            key="p97-primary-public",
            privacy="public",
        ),
        actor=p97_ready["publisher"],
    )["delivery"]
    assert claim(service, p97_ready, target) is None
    deferred = service.detail(delivery_request_id=public_delivery["id"])["delivery"]
    assert deferred["status"] == "queued"
    assert deferred["next_attempt_at"] > public_delivery["next_attempt_at"]


def test_fallback_scheduled_cancel_and_content_rules(p89_database, p97_ready) -> None:
    service = PlatformDeliveryService(p89_database)
    target = activate(
        service,
        target_request(
            key="simulated-fallback-target",
            configuration={"primary_behavior": "unsupported"},
        ),
        admin=p97_ready["admin"],
    )
    draft = service.create_delivery(
        delivery_request(
            p97_ready,
            target,
            key="p97-fallback-draft",
            delivery_mode="draft",
        ),
        actor=p97_ready["publisher"],
    )["delivery"]
    claimed = claim(service, p97_ready, target)
    assert claimed is not None
    succeeded = execute(service, p97_ready, claimed)
    assert succeeded["delivery"]["status"] == "succeeded"
    detail = service.detail(delivery_request_id=draft["id"])
    assert [item["transport"] for item in detail["attempts"]] == ["primary", "fallback"]
    assert detail["attempts"][-1]["platform_reference"].startswith("simulated+fallback://")
    reconciled = service.reconcile_delivery(
        delivery_request_id=draft["id"],
        actor=p97_ready["publisher"],
    )
    assert reconciled["reconciliation"]["platform_status"] == "draft"

    scheduled_for = datetime.now(timezone.utc) + timedelta(hours=2)
    scheduled = service.create_delivery(
        delivery_request(
            p97_ready,
            target,
            key="p97-scheduled-cancel",
            privacy="unlisted",
            delivery_mode="scheduled",
            scheduled_for=scheduled_for,
        ),
        actor=p97_ready["publisher"],
    )["delivery"]
    assert claim(service, p97_ready, target) is None
    cancelled = service.cancel_delivery(
        delivery_request_id=scheduled["id"],
        request=DeliveryCancelRequest(
            rationale="The controlled schedule changed before delivery."
        ),
        actor=p97_ready["publisher"],
    )
    assert cancelled["delivery"]["status"] == "cancelled"

    with pytest.raises(PlatformDeliveryError, match="delivery_disclosure_required"):
        service.create_delivery(
            delivery_request(
                p97_ready,
                target,
                key="p97-missing-disclosure",
                privacy="public",
                disclosure_text=None,
            ),
            actor=p97_ready["publisher"],
        )
    with pytest.raises(PlatformDeliveryError, match="delivery_thumbnail_not_current_or_available"):
        service.create_delivery(
            delivery_request(
                p97_ready,
                target,
                key="p97-invalid-thumbnail",
                privacy="public",
                thumbnail_artifact_version_id=p97_ready["output"]["id"],
            ),
            actor=p97_ready["publisher"],
        )
    with pytest.raises(PlatformDeliveryError, match="delivery_title_exceeds_target_limit"):
        service.create_delivery(
            delivery_request(
                p97_ready,
                target,
                key="p97-title-limit",
                privacy="public",
                title="x" * 101,
            ),
            actor=p97_ready["publisher"],
        )


class StatefulFlakyAdapter:
    adapter_key = "simulated-flaky"

    def __init__(self) -> None:
        self.calls = 0

    def deliver(self, request, *, target):
        self.calls += 1
        if self.calls == 1:
            raise DeliveryAdapterError(
                "simulated_flaky_retry",
                "The first controlled attempt fails and must retry.",
                retryable=True,
            )
        reference = f"simulated://flaky/{request.delivery_fingerprint[:24]}"
        return DeliveryAdapterResult(
            provider_request_id=f"flaky:{self.calls}",
            platform_reference=reference,
            response_payload={"simulated": True, "call": self.calls, "reference": reference},
        )

    def reconcile(self, request, *, platform_reference, target):
        return DeliveryReconciliationResult(
            platform_status=DeliveryPlatformStatus.PUBLISHED,
            response_payload={"simulated": True, "platform_reference": platform_reference},
        )


def test_retry_backoff_and_expired_lease_recovery(
    p89_database,
    p97_ready,
    monkeypatch,
) -> None:
    flaky = StatefulFlakyAdapter()
    service = PlatformDeliveryService(
        p89_database,
        adapters={"simulated-flaky": flaky},
    )
    retry_target = activate(
        service,
        target_request(
            key="simulated-retry-target",
            primary_adapter_key="simulated-flaky",
            fallback_adapter_key=None,
        ),
        admin=p97_ready["admin"],
    )
    delivery = service.create_delivery(
        delivery_request(p97_ready, retry_target, key="p97-retry-001"),
        actor=p97_ready["publisher"],
    )["delivery"]
    first_claim = claim(service, p97_ready, retry_target)
    assert first_claim is not None
    failed = execute(service, p97_ready, first_claim)
    assert failed["delivery"]["status"] == "retry_wait"
    assert failed["retry_scheduled"] is True

    future = datetime.now(timezone.utc) + timedelta(minutes=3)
    monkeypatch.setattr(delivery_service_module, "_utcnow", lambda: future)
    second_claim = claim(service, p97_ready, retry_target)
    assert second_claim is not None
    succeeded = execute(service, p97_ready, second_claim)
    assert succeeded["delivery"]["status"] == "succeeded"
    assert flaky.calls == 2
    assert len(service.detail(delivery_request_id=delivery["id"])["attempts"]) == 2

    stale_target = activate(
        service,
        target_request(
            key="simulated-stale-target",
            primary_adapter_key="simulated-flaky",
            fallback_adapter_key=None,
        ),
        admin=p97_ready["admin"],
    )
    stale = service.create_delivery(
        delivery_request(p97_ready, stale_target, key="p97-stale-private"),
        actor=p97_ready["publisher"],
    )["delivery"]
    next_delivery = service.create_delivery(
        delivery_request(
            p97_ready,
            stale_target,
            key="p97-stale-public",
            privacy="public",
        ),
        actor=p97_ready["publisher"],
    )["delivery"]
    stale_claim = claim(service, p97_ready, stale_target, lease_seconds=30)
    assert stale_claim is not None
    recovery_time = future + timedelta(minutes=2)
    monkeypatch.setattr(delivery_service_module, "_utcnow", lambda: recovery_time)
    next_claim = claim(service, p97_ready, stale_target)
    assert next_claim is not None
    assert next_claim["delivery"]["id"] == next_delivery["id"]
    stale_detail = service.detail(delivery_request_id=stale["id"])["delivery"]
    assert stale_detail["status"] == "retry_wait"
    assert stale_detail["last_error_code"] == "delivery_lease_expired"
