from __future__ import annotations

import pytest

from src.application.delivery import PlatformDeliveryService
from src.application.delivery.models import DeliveryClaimRequest, DeliveryExecuteRequest
from tests.integration.p97_delivery_support import (
    p89_database,
    p97_ready as p97_ready_fixture,
)
from tests.integration.test_p97_platform_delivery_lifecycle import (
    delivery_request,
    target_request,
)


pytestmark = pytest.mark.integration


def create_successful_delivery(
    service: PlatformDeliveryService,
    ready: dict[str, object],
    target: dict,
    *,
    key: str,
    title: str,
    caption: str,
    privacy: str,
) -> dict:
    created = service.create_delivery(
        delivery_request(
            ready,
            target,
            key=key,
            title=title,
            caption=caption,
            privacy=privacy,
        ),
        actor=ready["publisher"],
    )["delivery"]
    claimed = service.claim_due(
        DeliveryClaimRequest(
            worker_id=ready["publisher"],
            target_ids=(target["id"],),
            lease_seconds=120,
        ),
        allowed_brand_ids=(ready["brand_one"],),
    )
    assert claimed is not None
    assert claimed["delivery"]["id"] == created["id"]
    completed = service.execute_claim(
        DeliveryExecuteRequest(
            delivery_request_id=created["id"],
            worker_id=ready["publisher"],
            lease_token=claimed["lease_token"],
        )
    )
    assert completed["delivery"]["status"] == "succeeded"
    return completed["delivery"]


@pytest.fixture()
def p98_ready(p89_database, tmp_path) -> dict[str, object]:
    ready = p97_ready_fixture.__wrapped__(p89_database, tmp_path)
    delivery_service = PlatformDeliveryService(p89_database)
    target = delivery_service.create_target(
        target_request(
            key="p98-analytics-target",
            requests_per_minute=100,
            requests_per_day=1000,
        ),
        actor=ready["admin"],
    )["target"]
    target = delivery_service.activate_target(
        target_id=target["id"],
        actor=ready["admin"],
    )["target"]
    delivery_a = create_successful_delivery(
        delivery_service,
        ready,
        target,
        key="p98-delivery-variant-a",
        title="Variant A: direct factual hook",
        caption="A concise evidence-first caption for the controlled analytics variant.",
        privacy="private",
    )
    delivery_b = create_successful_delivery(
        delivery_service,
        ready,
        target,
        key="p98-delivery-variant-b",
        title="Variant B: curiosity-led hook",
        caption="A curiosity-led caption using the same approved media package.",
        privacy="unlisted",
    )
    return {
        **ready,
        "delivery_service": delivery_service,
        "analytics_target": target,
        "delivery_a": delivery_a,
        "delivery_b": delivery_b,
    }
