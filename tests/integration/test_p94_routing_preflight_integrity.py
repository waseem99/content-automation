from __future__ import annotations

import json
from decimal import Decimal

import psycopg
import pytest

from src.application.routing.models import RoutingPlanRequest
from src.application.routing.service import RoutingSpendService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import p91_ready
from tests.integration.p94_routing_lifecycle import activate_policy, mixed_inputs
from tests.integration.p94_routing_support import p94_ready


pytestmark = pytest.mark.integration


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

    with p89_database.connection() as conn:
        candidate = conn.execute(
            "SELECT asset_id FROM football_brief.visual_candidates WHERE id=%s",
            (
                next(
                    shot["selected_candidate_id"]
                    for shot in p94_ready["visual_shots"]
                    if str(shot["id"]) == str(managed.visual_shot_id)
                ),
            ),
        ).fetchone()

    request_payload = {
        "portfolio_content_id": str(p94_ready["content_one"]),
        "content_version": int(p94_ready["visual_project"]["content_version"]),
        "operation": "image_to_video",
        "format": "vertical_9_16",
        "duration_seconds": "5",
        "width": 704,
        "height": 1280,
        "fps": 24,
        "required_capabilities": ["camera_control", "character_consistency"],
        "input_asset_ids": [str(candidate["asset_id"])],
        "renderer_catalogue_entry_id": str(p94_ready["renderer_entry"]["id"]),
        "provider_key": None,
        "model_key": None,
        "request_metadata": {
            "visual_project_id": str(p94_ready["visual_project"]["id"]),
            "visual_shot_id": str(managed.visual_shot_id),
            "selected_candidate_id": str(
                next(
                    shot["selected_candidate_id"]
                    for shot in p94_ready["visual_shots"]
                    if str(shot["id"]) == str(managed.visual_shot_id)
                )
            ),
        },
    }
    with p89_database.transaction() as conn:
        zero_quote = conn.execute(
            """INSERT INTO football_brief.renderer_preflight_records
               (portfolio_content_id,content_version,renderer_catalogue_entry_id,operation,
                request_fingerprint,request_payload,accepted,rejection_reasons,estimated_cost,
                pricing_currency,expected_seconds,external_fee_possible,created_by)
               VALUES (%s,%s,%s,'image_to_video',%s,%s::jsonb,true,'[]'::jsonb,0,
                       'USD',40,false,%s)
               RETURNING id""",
            (
                p94_ready["content_one"],
                int(p94_ready["visual_project"]["content_version"]),
                p94_ready["renderer_entry"]["id"],
                "f" * 64,
                json.dumps(request_payload, sort_keys=True),
                p94_ready["producer"],
            ),
        ).fetchone()

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
