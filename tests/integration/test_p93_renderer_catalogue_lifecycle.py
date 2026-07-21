from decimal import Decimal
from uuid import UUID

import psycopg
import pytest

from src.application.renderers.models import (
    RendererCatalogueCreate,
    RendererHealth,
    RendererHealthUpdate,
    RendererOperation,
    RendererRepriceRequest,
    RendererResolveRequest,
    RendererSubmissionRequest,
    RendererSupportRequest,
)
from src.application.renderers.service import RendererCatalogueError, RendererCatalogueService
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def catalogue_request(*, key: str = "simulated-wan", behavior: str = "success") -> RendererCatalogueCreate:
    return RendererCatalogueCreate(
        renderer_key=key,
        display_name="Simulated Wan Production",
        adapter_key="simulated",
        operation=RendererOperation.IMAGE_TO_VIDEO,
        output_formats=("mp4",),
        min_duration_seconds=2,
        max_duration_seconds=12,
        max_width=1080,
        max_height=1920,
        capabilities=("camera_motion", "first_last_frame"),
        expected_seconds_base=30,
        expected_seconds_per_second=4,
        base_cost_usd=Decimal("0.25"),
        cost_per_second_usd=Decimal("0.10"),
        usage_evidence={"sample_count": 5, "source": "controlled P93 simulation"},
        health=RendererHealth.HEALTHY,
        quality_rating=Decimal("4.5"),
        simulated=True,
        execution_enabled=True,
        configuration={"simulation_behavior": behavior},
    )


def support_request() -> RendererSupportRequest:
    return RendererSupportRequest(
        operation=RendererOperation.IMAGE_TO_VIDEO,
        output_format="mp4",
        duration_seconds=8,
        width=1080,
        height=1920,
        required_capabilities=("camera_motion",),
    )


def test_renderer_lifecycle_resolution_repricing_and_immutable_history(p89_database, p89_seeded) -> None:
    service = RendererCatalogueService(p89_database)
    created = service.create_draft(catalogue_request(), actor=p89_seeded["admin"])
    renderer_id = created["renderer"]["id"]
    assert created["renderer"]["status"] == "draft"

    activated = service.activate(renderer_id=renderer_id, actor=p89_seeded["admin"])
    assert activated["renderer"]["status"] == "active"

    resolved = service.resolve(RendererResolveRequest(**support_request().model_dump()))
    assert resolved["renderer"]["id"] == renderer_id
    assert resolved["estimate"]["estimated_cost_usd"] == Decimal("1.050000")

    repriced = service.reprice(
        renderer_id=renderer_id,
        request=RendererRepriceRequest(
            base_cost_usd=Decimal("0.50"),
            cost_per_second_usd=Decimal("0.20"),
            reason="Controlled pricing revision from current usage evidence.",
        ),
        actor=p89_seeded["admin"],
    )
    replacement = repriced["renderer"]
    assert replacement["version"] == 2
    assert replacement["status"] == "active"
    assert repriced["retired_renderer"]["status"] == "retired"

    resolved_after = service.resolve(RendererResolveRequest(**support_request().model_dump()))
    assert resolved_after["renderer"]["id"] == replacement["id"]
    assert resolved_after["estimate"]["estimated_cost_usd"] == Decimal("2.100000")

    with pytest.raises(psycopg.Error, match="immutable"):
        with p89_database.transaction() as conn:
            conn.execute(
                "UPDATE football_brief.production_renderer_catalogue SET base_cost_usd=99 WHERE id=%s",
                (replacement["id"],),
            )


def test_simulated_success_and_failure_retain_exact_inputs(p89_database, p89_seeded) -> None:
    service = RendererCatalogueService(p89_database)
    success = service.create_draft(catalogue_request(key="simulated-success"), actor=p89_seeded["admin"])
    success_id = success["renderer"]["id"]
    service.activate(renderer_id=success_id, actor=p89_seeded["admin"])

    submitted = service.submit_simulated(
        RendererSubmissionRequest(
            renderer_id=success_id,
            idempotency_key="p93-success-001",
            request=support_request(),
            input_payload={"source_asset_id": "asset-one", "prompt": "approved motion prompt"},
        ),
        actor=p89_seeded["producer"],
    )
    assert submitted["attempt"]["status"] == "succeeded"
    assert submitted["attempt"]["catalogue_snapshot"]["renderer_key"] == "simulated-success"

    reused = service.submit_simulated(
        RendererSubmissionRequest(
            renderer_id=success_id,
            idempotency_key="p93-success-001",
            request=support_request(),
            input_payload={"source_asset_id": "asset-one", "prompt": "approved motion prompt"},
        ),
        actor=p89_seeded["producer"],
    )
    assert reused["reused"] is True

    failed = service.create_draft(
        catalogue_request(key="simulated-failure", behavior="fail"), actor=p89_seeded["admin"]
    )
    failed_id = failed["renderer"]["id"]
    service.activate(renderer_id=failed_id, actor=p89_seeded["admin"])
    with pytest.raises(RendererCatalogueError) as caught:
        service.submit_simulated(
            RendererSubmissionRequest(
                renderer_id=failed_id,
                idempotency_key="p93-failure-001",
                request=support_request(),
                input_payload={"source_asset_id": "asset-two", "prompt": "retained failing input"},
            ),
            actor=p89_seeded["producer"],
        )
    assert caught.value.code == "renderer_submission_failed"
    attempt_id = UUID(caught.value.details["attempt_id"])
    detail = service.attempt(attempt_id=attempt_id)
    assert detail["attempt"]["status"] == "failed"
    assert detail["attempt"]["input_payload"]["prompt"] == "retained failing input"
    assert detail["attempt"]["error_code"] == "simulated_renderer_failure"

    with pytest.raises(psycopg.Error, match="cannot be deleted"):
        with p89_database.transaction() as conn:
            conn.execute(
                "DELETE FROM football_brief.production_renderer_attempts WHERE id=%s",
                (attempt_id,),
            )


def test_health_and_unsupported_requests_fail_before_adapter_submission(p89_database, p89_seeded) -> None:
    service = RendererCatalogueService(p89_database)
    created = service.create_draft(catalogue_request(key="simulated-health"), actor=p89_seeded["admin"])
    renderer_id = created["renderer"]["id"]
    service.activate(renderer_id=renderer_id, actor=p89_seeded["admin"])
    service.update_health(
        renderer_id=renderer_id,
        request=RendererHealthUpdate(
            health=RendererHealth.UNAVAILABLE,
            quality_rating=Decimal("3.0"),
            usage_evidence={"last_probe": "failed"},
            reason="Controlled health probe marked the renderer unavailable.",
        ),
        actor=p89_seeded["admin"],
    )
    with pytest.raises(RendererCatalogueError) as caught:
        service.submit_simulated(
            RendererSubmissionRequest(
                renderer_id=renderer_id,
                idempotency_key="p93-blocked-001",
                request=support_request(),
                input_payload={"source_asset_id": "asset-three"},
            ),
            actor=p89_seeded["producer"],
        )
    assert caught.value.code == "renderer_submission_not_supported"
    assert "renderer_unavailable" in caught.value.details["reasons"]
    with p89_database.connection() as conn:
        count = conn.execute(
            "SELECT count(*) AS count FROM football_brief.production_renderer_attempts WHERE idempotency_key=%s",
            ("p93-blocked-001",),
        ).fetchone()["count"]
    assert count == 0
