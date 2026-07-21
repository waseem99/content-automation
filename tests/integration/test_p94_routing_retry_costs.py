from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.generation_jobs.models import GenerationJobCompletion, GenerationJobFailure
from src.application.generation_jobs.service import GenerationJobService
from src.application.routing.models import ReserveAndEnqueueRequest
from src.application.routing.service import RoutingSpendService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready
from tests.integration.p94_routing_lifecycle import (
    activate_policy,
    claim_managed_job,
    create_submit_approve,
    mixed_inputs,
)
from tests.integration.p94_routing_support import p94_ready


pytestmark = pytest.mark.integration


def test_retryable_failure_keeps_reservation_and_reconciles_cumulative_cost(
    p89_database,
    p94_ready,
) -> None:
    routing = RoutingSpendService(p89_database)
    jobs = GenerationJobService(p89_database)
    policy = activate_policy(routing, p94_ready, soft="8", hard="10", content="6")
    approved = create_submit_approve(
        routing,
        p94_ready,
        policy,
        mixed_inputs(p94_ready),
        ceiling=Decimal("4"),
    )
    managed = next(item for item in approved["items"] if item["route"] == "managed_render")
    enqueued = routing.reserve_and_enqueue(
        plan_id=approved["plan"]["id"],
        request=ReserveAndEnqueueRequest(
            routing_item_id=managed["id"],
            preferred_worker_id=p94_ready["producer"],
            max_attempts=2,
        ),
        actor=p94_ready["producer"],
    )

    first = claim_managed_job(p89_database, p94_ready)
    failed = jobs.fail(
        GenerationJobFailure(
            job_id=first["job"]["id"],
            attempt_id=first["attempt"]["id"],
            lease_token=first["lease_token"],
            worker_id=p94_ready["producer"],
            error_code="retryable_managed_failure",
            error_message="The first managed attempt incurred a fee and can be retried.",
            retryable=True,
            actual_cost_usd=Decimal("0.50"),
            error_details={"external_fee_incurred": True},
        )
    )
    assert failed["job"]["status"] == "failed"
    after_failure = routing.detail(plan_id=approved["plan"]["id"])
    held = after_failure["reservations"][0]
    assert held["id"] == enqueued["reservation"]["id"]
    assert held["status"] == "reserved"
    assert Decimal(str(held["actual_amount"])) == Decimal("0.500000")
    assert "reservation_retry_cost_recorded" in {
        event["event"] for event in after_failure["events"]
    }

    jobs.retry(job_id=first["job"]["id"], actor=p94_ready["producer"])
    second = claim_managed_job(p89_database, p94_ready)
    assert second["attempt"]["attempt_number"] == 2
    completed = jobs.complete(
        GenerationJobCompletion(
            job_id=second["job"]["id"],
            attempt_id=second["attempt"]["id"],
            lease_token=second["lease_token"],
            worker_id=p94_ready["producer"],
            output_payload={
                "provider_request_id": "managed-retry-success",
                "video_uri": "managed-test://retry-result.mp4",
                "external_fee_incurred": True,
            },
            provider_request_id="managed-retry-success",
            actual_cost_usd=Decimal("1.75"),
        )
    )
    assert completed["job"]["status"] == "succeeded"
    assert Decimal(str(completed["job"]["actual_cost_usd"])) == Decimal("2.250000")

    final = routing.detail(plan_id=approved["plan"]["id"])
    reservation = final["reservations"][0]
    assert reservation["status"] == "reconciled"
    assert Decimal(str(reservation["reserved_amount"])) == Decimal("2.000000")
    assert Decimal(str(reservation["actual_amount"])) == Decimal("2.250000")
    assert Decimal(str(reservation["overage_amount"])) == Decimal("0.250000")
