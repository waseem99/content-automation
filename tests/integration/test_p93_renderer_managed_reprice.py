from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.application.renderers.models import (
    RendererEntryRequest,
    RendererHealthRequest,
    RendererRepriceRequest,
)
from src.application.renderers.validated_service import ValidatedRendererCatalogueService
from tests.integration.p93_renderer_support import p93_database, p93_seeded


pytestmark = pytest.mark.integration


def managed_entry() -> RendererEntryRequest:
    return RendererEntryRequest(
        provider_key="managed-reprice-test",
        provider_display_name="Managed Reprice Test",
        model_key="managed-v1",
        model_display_name="Managed v1",
        operation="image_to_video",
        adapter_kind="http_api",
        supported_formats=("vertical_9_16",),
        min_duration_seconds=Decimal("2"),
        max_duration_seconds=Decimal("10"),
        duration_step_seconds=Decimal("1"),
        supported_resolutions=({"width": 704, "height": 1280},),
        capabilities={"camera_control": True},
        expected_latency_seconds={"p50": 30},
        pricing={"base_usd": "1"},
        pricing_currency="USD",
        quality_rating=Decimal("85"),
        commercial_use_allowed=True,
        usage_terms_url="https://example.test/managed-reprice-terms",
        usage_evidence_digest="f" * 64,
        usage_evidence_recorded_at=datetime.now(timezone.utc),
        data_handling={"retention_days": 7, "training_use": False},
    )


def test_managed_reprice_carries_health_as_append_only_evidence(p93_database, p93_seeded) -> None:
    service = ValidatedRendererCatalogueService(p93_database)
    created = service.create_entry(request=managed_entry(), actor=p93_seeded["admin"])["entry"]
    service.observe_health(
        entry_id=created["id"],
        request=RendererHealthRequest(
            status="healthy",
            latency_ms=1100,
            checked_by="managed-health-check",
            details={"source": "initial_provider_probe"},
        ),
        actor=p93_seeded["admin"],
    )
    parent = service.activate(entry_id=created["id"], actor=p93_seeded["admin"])["entry"]

    child = service.reprice(
        entry_id=parent["id"],
        request=RendererRepriceRequest(
            pricing={"base_usd": "1.50", "per_second_usd": "0.25"},
            rationale="Managed provider repriced its video operation",
            activate=True,
        ),
        actor=p93_seeded["admin"],
    )["entry"]

    assert child["version"] == 2
    assert child["status"] == "active"
    assert child["health_status"] == "healthy"
    assert service.detail(entry_id=parent["id"])["entry"]["status"] == "retired"
    child_detail = service.detail(entry_id=child["id"])
    assert len(child_detail["health_observations"]) == 1
    observation = child_detail["health_observations"][0]
    assert observation["status"] == "healthy"
    assert observation["details"]["source"] == "repricing_parent_health_carry_forward"
    assert observation["details"]["parent_entry_id"] == str(parent["id"])
