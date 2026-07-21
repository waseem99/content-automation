from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobFailure,
    GenerationJobType,
)
from src.application.generation_jobs.service import GenerationJobService
from src.application.routing.models import (
    BudgetPolicyRequest,
    ReserveAndEnqueueRequest,
    RoutingPlanRequest,
    ShotRoute,
    ShotRoutingInput,
    SpendDecision,
    SpendDecisionRequest,
)
from src.application.routing.service import RoutingSpendService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready
from tests.integration.p94_routing_support import p94_ready


pytestmark = pytest.mark.integration


def activate_policy(
    service: RoutingSpendService,
    ready,
    *,
    soft="3",
    hard="10",
    content="8",
) -> dict:
    created = service.create_policy(
        request=BudgetPolicyRequest(
            brand_id=ready["brand_one"],
            month_start=date(2026, 10, 1),
            monthly_soft_limit=Decimal(soft),
            monthly_hard_limit=Decimal(hard),
            default_content_limit=Decimal(content),
            approval_threshold=Decimal("1"),
            require_approval_for_managed=True,
        ),
        actor=ready["admin"],
    )["policy"]
    return service.activate_policy(policy_id=created["id"], actor=ready["admin"])["policy"]


def all_managed_inputs(ready) -> tuple[ShotRoutingInput, ...]:
    return tuple(
        ShotRoutingInput(
            visual_shot_id=shot["id"],
            renderer_preflight_id=ready["preflights"][str(shot["id"])]["id"],
            hero_importance=Decimal("90"),
            realism_requirement=Decimal("85"),
            motion_complexity=Decimal("80"),
            continuity_requirement=Decimal("90"),
            factual_control_requirement=Decimal("40"),
            local_preview_quality=Decimal("45"),
            engagement_contribution=Decimal("90"),
            forced_route=ShotRoute.MANAGED_RENDER,
            override_rationale="This integration route explicitly tests managed spend controls.",
        )
        for shot in ready["visual_shots"]
    )


def mixed_inputs(ready) -> tuple[ShotRoutingInput, ...]:
    items = []
    for index, shot in enumerate(ready["visual_shots"]):
        if index == 0:
            items.append(
                ShotRoutingInput(
                    visual_shot_id=shot["id"],
                    renderer_preflight_id=ready["preflights"][str(shot["id"])]["id"],
                    hero_importance=Decimal("90"),
                    realism_requirement=Decimal("85"),
                    motion_complexity=Decimal("80"),
                    continuity_requirement=Decimal("90"),
                    factual_control_requirement=Decimal("40"),
                    local_preview_quality=Decimal("45"),
                    engagement_contribution=Decimal("90"),
                    forced_route=ShotRoute.MANAGED_RENDER,
                    override_rationale="The hero shot requires managed realism and motion.",
                )
            )
        elif index == 1:
            items.append(
                ShotRoutingInput(
                    visual_shot_id=shot["id"],
                    local_preview_quality=Decimal("95"),
                    realism_requirement=Decimal("45"),
                    motion_complexity=Decimal("45"),
                    forced_route=ShotRoute.LOCAL_RENDER,
                    override_rationale="The approved local preview is sufficient for this supporting shot.",
                )
            )
        else:
            items.append(
                ShotRoutingInput(
                    visual_shot_id=shot["id"],
                    factual_control_requirement=Decimal("95"),
                    motion_complexity=Decimal("35"),
                    forced_route=ShotRoute.DETERMINISTIC_ANIMATION,
                    override_rationale="The explanatory mechanism requires deterministic factual control.",
                )
            )
    return tuple(items)


def create_submit_approve(service, ready, policy, shots, *, ceiling: Decimal) -> dict:
    plan = service.create_plan(
        content_id=ready["content_one"],
        request=RoutingPlanRequest(
            budget_policy_id=policy["id"],
            shots=shots,
            recommendation_context={"test": "p94-lifecycle"},
        ),
        actor=ready["producer"],
    )
    submitted = service.submit(
        plan_id=plan["plan"]["id"],
        expected_lock_version=plan["plan"]["lock_version"],
        actor=ready["producer"],
    )
    approved = service.decide(
        plan_id=plan["plan"]["id"],
        request=SpendDecisionRequest(
            expected_lock_version=submitted["plan"]["lock_version"],
            decision=SpendDecision.APPROVED,
            approved_ceiling=ceiling,
            rationale="The managed routes and exact ceiling are approved for this integration test.",
        ),
        reviewer=ready["reviewer"],
    )
    return approved


def claim_managed_job(database, ready):
    claimed = GenerationJobService(database).claim(
        worker_id=ready["producer"],
        allowed_brand_ids=[ready["brand_one"]],
        allowed_job_types=[GenerationJobType.PREMIUM_CLIP],
        requested_job_types=[GenerationJobType.PREMIUM_CLIP],
        providers=[ready["renderer_entry"]["provider_key"]],
        lease_seconds=120,
    )
    assert claimed is not None
    return claimed


def test_mixed_plan_requires_independent_approval_and_failed_job_releases_reservation(
    p89_database,
    p94_ready,
) -> None:
    service = RoutingSpendService(p89_database)
    policy = activate_policy(service, p94_ready, soft="1", hard="10", content="5")
    draft = service.create_plan(
        content_id=p94_ready["content_one"],
        request=RoutingPlanRequest(
            budget_policy_id=policy["id"],
            shots=mixed_inputs(p94_ready),
            recommendation_context={"strategy": "hero-only-managed"},
        ),
        actor=p94_ready["producer"],
    )
    assert {item["route"] for item in draft["items"]} >= {
        "managed_render", "local_render"
    }
    assert sum(Decimal(str(item["estimated_cost"])) for item in draft["items"]) == Decimal("2.000000")

    submitted = service.submit(
        plan_id=draft["plan"]["id"],
        expected_lock_version=draft["plan"]["lock_version"],
        actor=p94_ready["producer"],
    )
    assert submitted["plan"]["status"] == "in_review"
    assert Decimal(str(submitted["plan"]["total_estimated_cost"])) == Decimal("2.000000")
    assert submitted["plan"]["managed_shot_count"] == 1

    with pytest.raises(psycopg.Error, match="Independent spend review"):
        service.decide(
            plan_id=draft["plan"]["id"],
            request=SpendDecisionRequest(
                expected_lock_version=submitted["plan"]["lock_version"],
                decision=SpendDecision.APPROVED,
                approved_ceiling=Decimal("3"),
                rationale="Producer must not self-approve their routing plan.",
            ),
            reviewer=p94_ready["producer"],
        )
    assert service.detail(plan_id=draft["plan"]["id"])["decisions"] == []

    approved = service.decide(
        plan_id=draft["plan"]["id"],
        request=SpendDecisionRequest(
            expected_lock_version=submitted["plan"]["lock_version"],
            decision=SpendDecision.APPROVED,
            approved_ceiling=Decimal("3"),
            rationale="Reviewer approves one managed hero shot with a three-dollar ceiling.",
        ),
        reviewer=p94_ready["reviewer"],
    )
    managed = next(item for item in approved["items"] if item["route"] == "managed_render")
    enqueued = service.reserve_and_enqueue(
        plan_id=approved["plan"]["id"],
        request=ReserveAndEnqueueRequest(
            routing_item_id=managed["id"],
            preferred_worker_id=p94_ready["producer"],
            max_attempts=1,
        ),
        actor=p94_ready["producer"],
    )
    assert enqueued["reservation"]["soft_limit_exceeded"] is True
    assert enqueued["reservation"]["warnings"][0]["code"] == "MONTHLY_SOFT_LIMIT"
    reused = service.reserve_and_enqueue(
        plan_id=approved["plan"]["id"],
        request=ReserveAndEnqueueRequest(routing_item_id=managed["id"]),
        actor=p94_ready["producer"],
    )
    assert reused["reused"] is True
    assert reused["reservation"]["id"] == enqueued["reservation"]["id"]
    assert reused["job"]["id"] == enqueued["job"]["id"]

    claimed = claim_managed_job(p89_database, p94_ready)
    failed = GenerationJobService(p89_database).fail(
        GenerationJobFailure(
            job_id=claimed["job"]["id"],
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=p94_ready["producer"],
            error_code="managed_test_failure",
            error_message="Managed test failed without charging.",
            retryable=False,
            actual_cost_usd=Decimal("0"),
            error_details={"external_fee_incurred": False},
        )
    )
    assert failed["job"]["status"] == "dead_letter"
    final = service.detail(plan_id=approved["plan"]["id"])
    reservation = final["reservations"][0]
    assert reservation["status"] == "released"
    assert Decimal(str(reservation["actual_amount"])) == 0
    assert {event["event"] for event in final["events"]} >= {
        "reservation_created", "reservation_bound", "reservation_released"
    }


def test_success_reconciles_actual_cost_and_records_overage(p89_database, p94_ready) -> None:
    service = RoutingSpendService(p89_database)
    policy = activate_policy(service, p94_ready, soft="8", hard="10", content="6")
    approved = create_submit_approve(
        service,
        p94_ready,
        policy,
        mixed_inputs(p94_ready),
        ceiling=Decimal("4"),
    )
    managed = next(item for item in approved["items"] if item["route"] == "managed_render")
    enqueued = service.reserve_and_enqueue(
        plan_id=approved["plan"]["id"],
        request=ReserveAndEnqueueRequest(
            routing_item_id=managed["id"],
            preferred_worker_id=p94_ready["producer"],
        ),
        actor=p94_ready["producer"],
    )
    claimed = claim_managed_job(p89_database, p94_ready)
    completed = GenerationJobService(p89_database).complete(
        GenerationJobCompletion(
            job_id=claimed["job"]["id"],
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=p94_ready["producer"],
            output_payload={
                "provider_request_id": "managed-test-success",
                "video_uri": "managed-test://result.mp4",
                "external_fee_incurred": True,
            },
            provider_request_id="managed-test-success",
            actual_cost_usd=Decimal("2.50"),
        )
    )
    assert completed["job"]["status"] == "succeeded"
    final = service.detail(plan_id=approved["plan"]["id"])
    reservation = final["reservations"][0]
    assert reservation["id"] == enqueued["reservation"]["id"]
    assert reservation["status"] == "reconciled"
    assert Decimal(str(reservation["reserved_amount"])) == Decimal("2.000000")
    assert Decimal(str(reservation["actual_amount"])) == Decimal("2.500000")
    assert Decimal(str(reservation["overage_amount"])) == Decimal("0.500000")


def test_concurrent_reservations_serialize_against_monthly_hard_limit(p89_database, p94_ready) -> None:
    service = RoutingSpendService(p89_database)
    policy = activate_policy(service, p94_ready, soft="1", hard="3", content="3")
    approved = create_submit_approve(
        service,
        p94_ready,
        policy,
        all_managed_inputs(p94_ready),
        ceiling=Decimal(str(len(p94_ready["visual_shots"]) * 2)),
    )
    managed_items = [item for item in approved["items"] if item["route"] == "managed_render"]
    assert len(managed_items) >= 2

    def reserve(item):
        local_service = RoutingSpendService(p89_database)
        try:
            result = local_service.reserve_and_enqueue(
                plan_id=approved["plan"]["id"],
                request=ReserveAndEnqueueRequest(
                    routing_item_id=item["id"],
                    preferred_worker_id=p94_ready["producer"],
                ),
                actor=p94_ready["producer"],
            )
            return ("ok", result)
        except Exception as exc:  # PostgreSQL hard-stop evidence is asserted below.
            return ("error", str(exc))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, managed_items[:2]))

    assert [kind for kind, _ in results].count("ok") == 1
    assert [kind for kind, _ in results].count("error") == 1
    assert "Monthly managed-production hard limit exceeded" in next(
        payload for kind, payload in results if kind == "error"
    )
    final = service.detail(plan_id=approved["plan"]["id"])
    active = [item for item in final["reservations"] if item["status"] == "reserved"]
    assert len(active) == 1
    assert Decimal(str(active[0]["reserved_amount"])) == Decimal("2.000000")
