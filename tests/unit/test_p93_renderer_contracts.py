from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.application.renderers.adapters import RendererAdapterStatus, SimulatedRendererAdapter
from src.application.renderers.models import RendererCapabilityRequest, RendererEntryRequest
from tests.integration.p93_renderer_support import simulated_entry_request


def test_simulated_adapter_is_deterministic_and_zero_fee() -> None:
    adapter = SimulatedRendererAdapter()
    payload = {
        "operation": "image_to_video",
        "duration_seconds": 5,
        "width": 704,
        "height": 1280,
    }
    first = adapter.submit(payload)
    second = adapter.submit(payload)
    assert first.provider_request_id == second.provider_request_id
    assert first.request_fingerprint == second.request_fingerprint
    assert adapter.external_fee_possible is False
    assert adapter.health()["external_fee_possible"] is False
    completed = adapter.poll(first)
    assert completed.status == RendererAdapterStatus.SUCCEEDED
    assert completed.output_descriptor["external_fee_incurred"] is False


def test_simulated_adapter_preserves_deterministic_failure() -> None:
    adapter = SimulatedRendererAdapter()
    failed = adapter.submit({"operation": "image_to_video", "simulate_failure": True})
    assert failed.status == RendererAdapterStatus.FAILED
    assert failed.error_code == "simulated_failure"
    assert adapter.poll(failed) == failed


def test_renderer_entry_requires_simulated_provider_identity() -> None:
    payload = simulated_entry_request().model_dump()
    payload["provider_key"] = "not-simulated"
    with pytest.raises(ValueError, match="provider_key=simulated"):
        RendererEntryRequest(**payload)


def test_capability_request_rejects_conflicting_selectors() -> None:
    with pytest.raises(ValueError, match="entry id or provider/model"):
        RendererCapabilityRequest(
            portfolio_content_id=uuid4(),
            content_version=1,
            operation="image_to_video",
            format="vertical_9_16",
            duration_seconds=Decimal("5"),
            width=704,
            height=1280,
            renderer_catalogue_entry_id=uuid4(),
            provider_key="simulated",
        )
