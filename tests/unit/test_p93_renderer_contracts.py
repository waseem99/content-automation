from decimal import Decimal

import pytest

from src.application.renderers.adapters import RendererAdapterError, SimulatedProductionRendererAdapter
from src.application.renderers.models import (
    RendererCatalogueCreate,
    RendererOperation,
    RendererSubmissionRequest,
    RendererSupportRequest,
)
from src.application.renderers.service import evaluate_renderer_support


def active_entry(**overrides):
    entry = {
        "renderer_key": "simulated-wan",
        "version": 1,
        "adapter_key": "simulated",
        "operation": "image_to_video",
        "output_formats": ["mp4"],
        "min_duration_seconds": Decimal("2"),
        "max_duration_seconds": Decimal("12"),
        "max_width": 1080,
        "max_height": 1920,
        "capabilities": ["camera_motion", "first_last_frame"],
        "expected_seconds_base": Decimal("30"),
        "expected_seconds_per_second": Decimal("4"),
        "base_cost_usd": Decimal("0.250000"),
        "cost_per_second_usd": Decimal("0.100000"),
        "health": "healthy",
        "quality_rating": Decimal("4.50"),
        "status": "active",
        "simulated": True,
        "execution_enabled": True,
        "configuration": {},
    }
    entry.update(overrides)
    return entry


def request(**overrides):
    values = {
        "operation": RendererOperation.IMAGE_TO_VIDEO,
        "output_format": "mp4",
        "duration_seconds": Decimal("8"),
        "width": 1080,
        "height": 1920,
        "required_capabilities": ("camera_motion",),
    }
    values.update(overrides)
    return RendererSupportRequest(**values)


def test_catalogue_model_rejects_live_execution_and_wrong_simulated_adapter() -> None:
    common = dict(
        renderer_key="wan-production",
        display_name="Wan Production",
        operation=RendererOperation.IMAGE_TO_VIDEO,
        output_formats=("mp4",),
        max_duration_seconds=10,
        max_width=1080,
        max_height=1920,
    )
    with pytest.raises(ValueError, match="only permits execution"):
        RendererCatalogueCreate(adapter_key="external", execution_enabled=True, **common)
    with pytest.raises(ValueError, match="simulated adapter"):
        RendererCatalogueCreate(adapter_key="external", simulated=True, **common)


def test_support_evaluation_checks_every_declared_dimension_and_estimates() -> None:
    evaluation = evaluate_renderer_support(active_entry(), request(), for_submission=True)
    assert evaluation["supported"] is True
    assert evaluation["expected_seconds"] == Decimal("62.000")
    assert evaluation["estimated_cost_usd"] == Decimal("1.050000")

    blocked = evaluate_renderer_support(
        active_entry(health="unavailable"),
        request(
            output_format="webm",
            duration_seconds=20,
            width=1440,
            required_capabilities=("lip_sync",),
        ),
        for_submission=True,
    )
    assert blocked["supported"] is False
    assert set(blocked["reasons"]) >= {
        "renderer_unavailable",
        "format_not_supported",
        "duration_not_supported",
        "resolution_not_supported",
        "capability_not_supported",
    }
    assert blocked["missing_capabilities"] == ["lip_sync"]


def test_submission_boundary_blocks_unverified_or_live_entries() -> None:
    unknown = evaluate_renderer_support(active_entry(health="unknown"), request(), for_submission=True)
    assert "renderer_health_unverified" in unknown["reasons"]
    disabled = evaluate_renderer_support(
        active_entry(execution_enabled=False, simulated=False), request(), for_submission=True
    )
    assert "renderer_execution_disabled" in disabled["reasons"]
    assert "live_renderer_submission_not_enabled" in disabled["reasons"]


def test_simulated_adapter_is_deterministic_and_can_fail_without_external_calls() -> None:
    submission = RendererSubmissionRequest(
        renderer_id="00000000-0000-0000-0000-000000000001",
        idempotency_key="p93-simulation-001",
        request=request(),
        input_payload={"source_asset_id": "asset-1"},
    )
    adapter = SimulatedProductionRendererAdapter()
    result = adapter.submit(submission, catalogue_entry=active_entry())
    assert result.provider_request_id == "simulated:p93-simulation-001"
    assert result.actual_cost_usd == 0
    assert result.output_payload["simulated"] is True

    with pytest.raises(RendererAdapterError, match="configured to fail"):
        adapter.submit(
            submission,
            catalogue_entry=active_entry(configuration={"simulation_behavior": "fail"}),
        )
