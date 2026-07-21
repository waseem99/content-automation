from __future__ import annotations

import json
from decimal import Decimal

import psycopg
import pytest

from src.application.routing.models import RoutingPlanRequest
from src.application.routing.service import RoutingSpendService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready
from tests.integration.test_p94_routing_lifecycle import activate_policy, mixed_inputs
from tests.integration.p94_routing_support import p94_ready


pytestmark = pytest.mark.integration


def managed_request_payload(database, ready, managed) -> dict:
    selected_candidate_id = next(
        shot["selected_candidate_id"]
        for shot in ready["visual_shots"]
        if str(shot["id"]) == str(managed.visual_shot_id)
    )
    with database.connection() as conn:
        candidate = conn.execute(
            "SELECT asset_id FROM football_brief.visual_candidates WHERE id=%s",
            (selected_candidate_id,),
        ).fetchone()
    return {
        "portfolio_content_id": str(ready["content_one"]),
        "content_version": int(ready["visual_project"]["content_version"]),
        "operation": "image_to_video",
        "format": "vertical_9_16",
        "duration_seconds": "5",
        "width": 704,
        "height": 1280,
        "fps": 24,
        "required_capabilities": ["camera_control", "character_consistency"],
        "input_asset_ids": [str(candidate["asset_id"])],
        "renderer_catalogue_entry_id": str(ready["renderer_entry"]["id"]),
        "provider_key": None,
        "model_key": None,
        "request_metadata": {
            "visual_project_id": str(ready["visual_project"]["id"]),
            "visual_shot_id": str(managed.visual_shot_id),
            "selected_candidate_id": str(selected_candidate_id),
        },
    }


def insert_managed_preflight(
    database,
    ready,
    *,
    request_payload: dict,
    fingerprint: str,
    estimated_cost: str,
    pricing_currency: str,
    external_fee_possible: bool,
):
    with database.transaction() as conn:
        return conn.execute(
            """INSERT INTO football_brief.renderer_preflight_records
               (portfolio_content_id,content_version,renderer_catalogue_entry_id,operation,
                request_fingerprint,request_payload,accepted,rejection_reasons,estimated_cost,
                pricing_currency,expected_seconds,external_fee_possible,created_by)
               VALUES (%s,%s,%s,'image_to_video',%s,%s::jsonb,true,'[]'::jsonb,%s,
                       %s,40,%s,%s)
               RETURNING id""",
            (
                ready["content_one"],
                int(ready["visual_project"]["content_version"]),
                ready["renderer_entry"]["id"],
                fingerprint,
                json.dumps(request_payload, sort_keys=True),
                estimated_cost,
                pricing_currency,
                external_fee_possible,
                ready["producer"],
            ),
        ).fetchone()


def test_managed_route_rejects_preflight_from_another_approved_shot(
    p89_database,
    p94_ready,
) -> None:
    service = RoutingSpendService(p89_database)
    policy = activate_policy(service, p94_ready)
    inputs = list(mixed_inputs(p94_ready))
    managed = inputs[0]
    other_shot = next(
        shot for shot in p94_ready["visual_shots"]
        if str(shot["id"]) != str(managed.visual_shot_id)
    )
    inputs[0] = managed.model_copy(
        update={
            "renderer_preflight_id": p94_ready["preflights"][str(other_shot["id"])]["id"]
        }
    )

    with pytest.raises(psycopg.Error, match="exact approved local candidate input"):
        service.create_plan(
            content_id=p94_ready["content_one"],
            request=RoutingPlanRequest(
                budget_policy_id=policy["id"],
                shots=tuple(inputs),
                recommendation_context={"test": "cross-shot-preflight-rejected"},
            ),
            actor=p94_ready["producer"],
        )


def test_managed_route_rejects_quote_without_known_external_fee(
    p89_database,
    p94_ready,
) -> None:
    service = RoutingSpendService(p89_database)
    policy = activate_policy(service, p94_ready)
    inputs = list(mixed_inputs(p94_ready))
    managed = inputs[0]
    zero_quote = insert_managed_preflight(
        p89_database,
        p94_ready,
        request_payload=managed_request_payload(p89_database, p94_ready, managed),
        fingerprint="f" * 64,
        estimated_cost="0",
        pricing_currency="USD",
        external_fee_possible=False,
    )

    inputs[0] = managed.model_copy(update={"renderer_preflight_id": zero_quote["id"]})
    with pytest.raises(psycopg.Error, match="known positive external fee"):
        service.create_plan(
            content_id=p94_ready["content_one"],
            request=RoutingPlanRequest(
                budget_policy_id=policy["id"],
                shots=tuple(inputs),
                recommendation_context={"test": "unknown-managed-price-rejected"},
            ),
            actor=p94_ready["producer"],
        )


def test_managed_route_rejects_non_usd_quote_against_usd_budget(
    p89_database,
    p94_ready,
) -> None:
    service = RoutingSpendService(p89_database)
    policy = activate_policy(service, p94_ready)
    inputs = list(mixed_inputs(p94_ready))
    managed = inputs[0]
    foreign_quote = insert_managed_preflight(
        p89_database,
        p94_ready,
        request_payload=managed_request_payload(p89_database, p94_ready, managed),
        fingerprint="e" * 64,
        estimated_cost="2",
        pricing_currency="EUR",
        external_fee_possible=True,
    )

    inputs[0] = managed.model_copy(update={"renderer_preflight_id": foreign_quote["id"]})
    with pytest.raises(psycopg.Error, match="must use USD"):
        service.create_plan(
            content_id=p94_ready["content_one"],
            request=RoutingPlanRequest(
                budget_policy_id=policy["id"],
                shots=tuple(inputs),
                recommendation_context={"test": "currency-mismatch-rejected"},
            ),
            actor=p94_ready["producer"],
        )
