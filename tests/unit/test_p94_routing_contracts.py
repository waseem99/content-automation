from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.routing.models import ShotRoute, ShotRoutingInput
from src.application.routing.service import RoutingSpendError, RoutingSpendService


def route(**overrides):
    payload = {
        "visual_shot_id": uuid4(),
        "hero_importance": Decimal("20"),
        "realism_requirement": Decimal("20"),
        "motion_complexity": Decimal("20"),
        "continuity_requirement": Decimal("50"),
        "factual_control_requirement": Decimal("20"),
        "local_preview_quality": Decimal("80"),
        "engagement_contribution": Decimal("30"),
    }
    payload.update(overrides)
    return ShotRoutingInput(**payload)


def managed_preflight(*, accepted=True):
    return {
        "id": uuid4(),
        "accepted": accepted,
        "estimated_cost": Decimal("2"),
        "provider_key": "managed-p94-test",
        "model_key": "managed-p94-video-v1",
    }


def test_high_factual_control_routes_to_deterministic_animation() -> None:
    selected, rationale, alternatives = RoutingSpendService._recommend_route(
        route(factual_control_requirement=Decimal("90"), motion_complexity=Decimal("40")),
        managed_preflight(),
    )
    assert selected == ShotRoute.DETERMINISTIC_ANIMATION
    assert "factual-control" in rationale
    assert any(item["route"] == ShotRoute.MANAGED_RENDER.value for item in alternatives)


def test_good_local_preview_routes_to_zero_cost_local_render() -> None:
    selected, rationale, _ = RoutingSpendService._recommend_route(
        route(local_preview_quality=Decimal("90"), realism_requirement=Decimal("55")),
        managed_preflight(),
    )
    assert selected == ShotRoute.LOCAL_RENDER
    assert "local quality" in rationale


def test_high_value_complex_shot_routes_to_managed_when_preflight_is_accepted() -> None:
    selected, rationale, alternatives = RoutingSpendService._recommend_route(
        route(
            hero_importance=Decimal("90"),
            realism_requirement=Decimal("85"),
            motion_complexity=Decimal("80"),
            local_preview_quality=Decimal("40"),
            engagement_contribution=Decimal("90"),
            renderer_preflight_id=uuid4(),
        ),
        managed_preflight(),
    )
    assert selected == ShotRoute.MANAGED_RENDER
    assert "justifies managed rendering" in rationale
    assert any(item["route"] == ShotRoute.LOCAL_RENDER.value for item in alternatives)


def test_unsatisfied_automatic_route_falls_back_to_manual_edit() -> None:
    selected, _, alternatives = RoutingSpendService._recommend_route(
        route(
            realism_requirement=Decimal("85"),
            motion_complexity=Decimal("85"),
            local_preview_quality=Decimal("30"),
        ),
        None,
    )
    assert selected == ShotRoute.MANUAL_EDIT
    assert not any(item["route"] == ShotRoute.MANAGED_RENDER.value for item in alternatives)


def test_managed_override_requires_accepted_preflight() -> None:
    item = route(
        forced_route=ShotRoute.MANAGED_RENDER,
        override_rationale="Hero shot requires a managed render.",
        renderer_preflight_id=uuid4(),
    )
    with pytest.raises(RoutingSpendError, match="forced_managed_route_requires_accepted_preflight"):
        RoutingSpendService._recommend_route(item, None)
