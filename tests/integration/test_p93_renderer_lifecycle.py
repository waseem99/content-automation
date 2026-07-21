from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.generation_jobs.models import GenerationJobFailure, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.application.renderers.adapters import SimulatedRendererAdapter
from src.application.renderers.models import (
    RendererCapabilityRequest,
    RendererHealthRequest,
    RendererRepriceRequest,
    SimulatedJobRequest,
)
from src.application.renderers.service import RendererCatalogueError, RendererCatalogueService
from tests.integration.p93_renderer_support import p93_database, p93_seeded, simulated_entry_request


pytestmark = pytest.mark.integration


def supported_request(seeded, *, entry_id=None, format_name="vertical_9_16", duration="5"):
    return RendererCapabilityRequest(
        portfolio_content_id=seeded["content_one"],
        content_version=seeded["content_one_version"],
        operation="image_to_video",
        format=format_name,
        duration_seconds=Decimal(duration),
        width=704,
        height=1280,
        required_capabilities=("camera_control", "character_consistency"),
        renderer_catalogue_entry_id=entry_id,
        request_metadata={"shot_id": "S01", "source": "p93-test"},
    )


def activate_simulated(service, seeded):
    created = service.create_entry(
        request=simulated_entry_request(),
        actor=seeded["admin"],
    )
    return service.activate(entry_id=created["entry"]["id"], actor=seeded["admin"])["entry"]


def test_versioned_reprice_preserves_quotes_and_switches_active_entry(p93_database, p93_seeded) -> None:
    service = RendererCatalogueService(p93_database)
    first = activate_simulated(service, p93_seeded)
    first_preflight = service.preflight(
        request=supported_request(p93_seeded),
        actor=p93_seeded["producer"],
    )["preflight"]
    assert first_preflight["accepted"] is True
    assert first_preflight["renderer_catalogue_entry_id"] == first["id"]
    assert Decimal(str(first_preflight["estimated_cost"])) == 0

    repriced = service.reprice(
        entry_id=first["id"],
        request=RendererRepriceRequest(
            pricing={"base_usd": "1.25", "per_second_usd": "0.10"},
            rationale="Updated simulated benchmark pricing",
            activate=True,
        ),
        actor=p93_seeded["admin"],
    )["entry"]
    assert repriced["version"] == 2
    assert repriced["parent_entry_id"] == first["id"]
    assert repriced["status"] == "active"
    assert service.detail(entry_id=first["id"])["entry"]["status"] == "retired"

    second_preflight = service.preflight(
        request=supported_request(p93_seeded),
        actor=p93_seeded["producer"],
    )["preflight"]
    assert second_preflight["renderer_catalogue_entry_id"] == repriced["id"]
    assert Decimal(str(second_preflight["estimated_cost"])) == Decimal("1.750000")

    with p93_database.connection() as conn:
        preserved = conn.execute(
            "SELECT * FROM football_brief.renderer_preflight_records WHERE id=%s",
            (first_preflight["id"],),
        ).fetchone()
    assert preserved["renderer_catalogue_entry_id"] == first["id"]
    assert Decimal(str(preserved["estimated_cost"])) == 0

    with pytest.raises(Exception, match="immutable"):
        with p93_database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.renderer_catalogue_entries SET pricing='{\"base_usd\":99}'::jsonb WHERE id=%s",
                (repriced["id"],),
            )


def test_unsupported_and_unhealthy_requests_are_recorded_and_never_enqueued(p93_database, p93_seeded) -> None:
    service = RendererCatalogueService(p93_database)
    entry = activate_simulated(service, p93_seeded)

    unsupported = service.preflight(
        request=supported_request(p93_seeded, format_name="horizontal_16_9", duration="11"),
        actor=p93_seeded["producer"],
    )["preflight"]
    assert unsupported["accepted"] is False
    assert "unsupported_format" in unsupported["rejection_reasons"]
    assert "unsupported_duration" in unsupported["rejection_reasons"]
    with pytest.raises(RendererCatalogueError) as rejected:
        service.enqueue_simulated(
            request=SimulatedJobRequest(renderer_preflight_id=unsupported["id"]),
            actor=p93_seeded["producer"],
        )
    assert rejected.value.code == "renderer_preflight_rejected"

    service.observe_health(
        entry_id=entry["id"],
        request=RendererHealthRequest(
            status="unavailable",
            latency_ms=9000,
            checked_by="p93-health-test",
            details={"reason": "simulated outage"},
        ),
        actor=p93_seeded["admin"],
    )
    unavailable = service.preflight(
        request=supported_request(p93_seeded),
        actor=p93_seeded["producer"],
    )["preflight"]
    assert unavailable["accepted"] is False
    assert unavailable["rejection_reasons"] == ["renderer_unavailable"]

    with p93_database.connection() as conn:
        jobs = conn.execute("SELECT count(*) AS count FROM football_brief.generation_jobs").fetchone()
    assert jobs["count"] == 0


def test_simulated_failure_retains_exact_job_attempt_input_and_events(p93_database, p93_seeded) -> None:
    catalogue = RendererCatalogueService(p93_database)
    activate_simulated(catalogue, p93_seeded)
    preflight = catalogue.preflight(
        request=supported_request(p93_seeded),
        actor=p93_seeded["producer"],
    )["preflight"]
    enqueued = catalogue.enqueue_simulated(
        request=SimulatedJobRequest(
            renderer_preflight_id=preflight["id"],
            preferred_worker_id=p93_seeded["producer"],
            max_attempts=1,
        ),
        actor=p93_seeded["producer"],
    )
    job_id = enqueued["job"]["id"]

    jobs = GenerationJobService(p93_database)
    claimed = jobs.claim(
        worker_id=p93_seeded["producer"],
        allowed_brand_ids=[p93_seeded["brand_one"]],
        allowed_job_types=[GenerationJobType.PREMIUM_CLIP],
        requested_job_types=[GenerationJobType.PREMIUM_CLIP],
        providers=["simulated"],
        lease_seconds=120,
    )
    assert claimed is not None
    assert claimed["job"]["id"] == job_id
    submission = SimulatedRendererAdapter().submit(
        {**dict(claimed["job"]["input_payload"]), "simulate_failure": True}
    )
    failed = jobs.fail(
        GenerationJobFailure(
            job_id=job_id,
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=p93_seeded["producer"],
            error_code=submission.error_code or "simulated_failure",
            error_message=submission.error_message or "Simulated failure",
            retryable=False,
            actual_cost_usd=Decimal("0"),
            error_details={
                "provider_request_id": submission.provider_request_id,
                "request_fingerprint": submission.request_fingerprint,
                "external_fee_incurred": False,
            },
        )
    )
    assert failed["job"]["status"] == "dead_letter"
    detail = jobs.detail(job_id=job_id)
    assert detail["job"]["input_payload"]["renderer_preflight_id"] == str(preflight["id"])
    assert len(detail["attempts"]) == 1
    assert detail["attempts"][0]["status"] == "failed"
    assert detail["attempts"][0]["input_fingerprint"] == detail["job"]["input_fingerprint"]
    assert {event["event"] for event in detail["events"]} >= {
        "enqueued", "claimed", "failed", "dead_lettered"
    }
    with p93_database.connection() as conn:
        binding = conn.execute(
            "SELECT * FROM football_brief.renderer_job_bindings WHERE generation_job_id=%s",
            (job_id,),
        ).fetchone()
    assert binding["renderer_preflight_id"] == preflight["id"]
    assert binding["renderer_catalogue_entry_id"] == preflight["renderer_catalogue_entry_id"]
