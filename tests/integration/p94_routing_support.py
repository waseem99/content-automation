from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from src.application.renderers.models import (
    RendererCapabilityRequest,
    RendererEntryRequest,
    RendererHealthRequest,
)
from src.application.renderers.validated_service import ValidatedRendererCatalogueService
from src.application.visuals.models import (
    CandidateDecision,
    CandidateDecisionRequest,
    CandidateResult,
    ProjectDecision,
    ProjectDecisionRequest,
    SubmitProjectRequest,
)
from src.application.visuals.review_service import VisualReviewService
from src.application.visuals.validated_service import ValidatedVisualProjectService
from tests.integration.p89_script_support import p89_database, p89_seeded
from tests.integration.p91_visual_support import (
    candidate_checks,
    complete_next_keyframe_job,
    p91_ready,
    project_request,
    register_image_asset,
)


pytestmark = pytest.mark.integration


def managed_renderer_request() -> RendererEntryRequest:
    return RendererEntryRequest(
        provider_key="managed-p94-test",
        provider_display_name="Managed P94 Test",
        model_key="managed-p94-video-v1",
        model_display_name="Managed P94 Video v1",
        operation="image_to_video",
        adapter_kind="http_api",
        supported_formats=("vertical_9_16",),
        min_duration_seconds=Decimal("2"),
        max_duration_seconds=Decimal("10"),
        duration_step_seconds=Decimal("1"),
        supported_resolutions=({"width": 704, "height": 1280},),
        capabilities={
            "camera_control": True,
            "character_consistency": True,
            "negative_prompt": True,
        },
        expected_latency_seconds={"p50": 30, "p95": 90, "per_output_second": 2},
        pricing={"base_usd": "1", "per_second_usd": "0.20"},
        pricing_currency="USD",
        quality_rating=Decimal("90"),
        commercial_use_allowed=True,
        usage_terms_url="https://example.test/p94-managed-terms",
        usage_evidence_digest="9" * 64,
        usage_evidence_recorded_at=datetime.now(timezone.utc),
        data_handling={"retention_days": 7, "training_use": False},
        notes="Integration-only managed catalogue record. No provider credential is used.",
    )


@pytest.fixture()
def p94_ready(p89_database, p91_ready) -> dict[str, object]:
    visuals = ValidatedVisualProjectService(p89_database)
    review = VisualReviewService(p89_database)
    detail = visuals.initialize(
        content_id=p91_ready["content_one"],
        request=project_request(p91_ready, base_seed=951000),
        actor=p91_ready["producer"],
    )

    while any(candidate["status"] == "queued" for candidate in detail["candidates"]):
        job = complete_next_keyframe_job(
            p89_database,
            worker=p91_ready["producer"],
            brand_id=p91_ready["brand_one"],
        )
        detail = visuals.detail(project_id=detail["project"]["id"])
        candidate = next(
            item for item in detail["candidates"]
            if str(item["generation_job_id"]) == str(job["id"])
        )
        asset_id = register_image_asset(
            p89_database,
            key=f"p94-candidate-{candidate['id']}",
            created_by=p91_ready["producer"],
        )
        detail = visuals.register_candidate_result(
            candidate_id=candidate["id"],
            result=CandidateResult(
                asset_id=asset_id,
                width=int(candidate["width"]),
                height=int(candidate["height"]),
                provenance={
                    "local": True,
                    "provider": candidate["provider"],
                    "model_id": candidate["model_id"],
                    "seed": int(candidate["seed"]),
                    "workflow_digest": "7" * 64,
                    "external_fee_incurred": False,
                },
                checks=candidate_checks(),
            ),
            actor=p91_ready["producer"],
        )

    for shot in detail["shots"]:
        candidate = next(
            item for item in detail["candidates"]
            if str(item["visual_shot_version_id"]) == str(shot["current_version_id"])
            and item["checks_status"] == "pass"
        )
        detail = review.decide_candidate(
            project_id=detail["project"]["id"],
            shot_id=shot["id"],
            shot_version_id=shot["current_version_id"],
            candidate_id=candidate["id"],
            request=CandidateDecisionRequest(
                expected_shot_lock_version=shot["lock_version"],
                decision=CandidateDecision.SELECTED,
                rationale="Candidate passed all ten technical and continuity checks for P94 routing.",
            ),
            reviewer=p91_ready["reviewer"],
        )

    submitted = review.submit_project(
        project_id=detail["project"]["id"],
        request=SubmitProjectRequest(
            expected_project_lock_version=detail["project"]["lock_version"]
        ),
        actor=p91_ready["producer"],
    )
    approved = review.decide_project(
        project_id=detail["project"]["id"],
        request=ProjectDecisionRequest(
            expected_project_lock_version=submitted["project"]["lock_version"],
            decision=ProjectDecision.APPROVED,
            rationale="Every selected local candidate passed continuity review and is approved for routing.",
        ),
        reviewer=p91_ready["reviewer"],
    )

    catalogue = ValidatedRendererCatalogueService(p89_database)
    renderer = catalogue.create_entry(
        request=managed_renderer_request(),
        actor=p91_ready["admin"],
    )["entry"]
    catalogue.observe_health(
        entry_id=renderer["id"],
        request=RendererHealthRequest(
            status="healthy",
            latency_ms=1500,
            checked_by="p94-managed-health",
            details={"source": "integration_fixture", "live_request": False},
        ),
        actor=p91_ready["admin"],
    )
    renderer = catalogue.activate(
        entry_id=renderer["id"],
        actor=p91_ready["admin"],
    )["entry"]

    preflights = {}
    for shot in approved["shots"]:
        selected_candidate = next(
            item for item in approved["candidates"]
            if str(item["id"]) == str(shot["selected_candidate_id"])
        )
        preflight = catalogue.preflight(
            request=RendererCapabilityRequest(
                portfolio_content_id=p91_ready["content_one"],
                content_version=int(approved["project"]["content_version"]),
                operation="image_to_video",
                format="vertical_9_16",
                duration_seconds=Decimal("5"),
                width=704,
                height=1280,
                required_capabilities=("camera_control", "character_consistency"),
                input_asset_ids=(selected_candidate["asset_id"],),
                renderer_catalogue_entry_id=renderer["id"],
                request_metadata={
                    "visual_project_id": str(approved["project"]["id"]),
                    "visual_shot_id": str(shot["id"]),
                    "selected_candidate_id": str(shot["selected_candidate_id"]),
                },
            ),
            actor=p91_ready["producer"],
        )["preflight"]
        assert preflight["accepted"] is True
        assert Decimal(str(preflight["estimated_cost"])) == Decimal("2.000000")
        preflights[str(shot["id"])] = preflight

    return {
        **p91_ready,
        "visual_project": approved["project"],
        "visual_shots": approved["shots"],
        "renderer_entry": renderer,
        "preflights": preflights,
    }
