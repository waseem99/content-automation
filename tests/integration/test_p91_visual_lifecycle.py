from __future__ import annotations

from decimal import Decimal

import psycopg
import pytest

from src.application.generation_jobs.models import GenerationJobEnqueue, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.application.visuals.models import (
    CandidateCheckType,
    CandidateDecision,
    CandidateDecisionRequest,
    CandidateResult,
    ProjectDecision,
    ProjectDecisionRequest,
    ShotDecision,
    ShotDecisionRequest,
    ShotRevisionRequest,
    SubmitProjectRequest,
)
from src.application.visuals.review_service import VisualReviewService
from src.application.visuals.validated_service import ValidatedVisualProjectService
from tests.integration.p91_visual_support import (
    candidate_checks,
    complete_next_keyframe_job,
    p89_database,
    p89_seeded,
    p91_ready,
    project_request,
    register_image_asset,
)


pytestmark = pytest.mark.integration


def register_all_candidates(database, ready, service, detail, *, failed_candidate_id=None):
    registered = detail
    while any(candidate["status"] == "queued" for candidate in registered["candidates"]):
        job = complete_next_keyframe_job(
            database,
            worker=ready["producer"],
            brand_id=ready["brand_one"],
        )
        registered = service.detail(project_id=detail["project"]["id"])
        candidate = next(
            item for item in registered["candidates"]
            if str(item["generation_job_id"]) == str(job["id"])
        )
        asset_id = register_image_asset(
            database,
            key=f"candidate-{candidate['id']}",
            created_by=ready["producer"],
        )
        failed_check = (
            CandidateCheckType.SUBJECT_CONSISTENCY
            if failed_candidate_id is not None and str(candidate["id"]) == str(failed_candidate_id)
            else None
        )
        registered = service.register_candidate_result(
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
                    "workflow_digest": "c" * 64,
                    "external_fee_incurred": False,
                },
                checks=candidate_checks(failed_check=failed_check),
            ),
            actor=ready["producer"],
        )
    return registered


def select_candidate(review, detail, *, shot, candidate, reviewer):
    return review.decide_candidate(
        project_id=detail["project"]["id"],
        shot_id=shot["id"],
        shot_version_id=shot["current_version_id"],
        candidate_id=candidate["id"],
        request=CandidateDecisionRequest(
            expected_shot_lock_version=shot["lock_version"],
            decision=CandidateDecision.SELECTED,
            rationale="Candidate passes all technical, prompt, duplicate, continuity, palette, lighting, landmark, and framing checks.",
        ),
        reviewer=reviewer,
    )


def preview_enqueue(ready, detail, selected_candidate_id):
    project = detail["project"]
    return GenerationJobEnqueue(
        portfolio_content_id=project["portfolio_content_id"],
        content_version=int(project["content_version"]),
        production_workflow_id=project["workflow_id"],
        production_workflow_version_id=project["workflow_version_id"],
        job_type=GenerationJobType.PREVIEW,
        provider="local-preview",
        model_id="local-ken-burns-v1",
        idempotency_key=f"p91:preview:{project['id']}:{selected_candidate_id}",
        input_payload={
            "script_version_id": str(project["script_version_id"]),
            "visual_project_id": str(project["id"]),
            "visual_candidate_id": str(selected_candidate_id),
            "runtime": "local_preview",
            "external_fee_allowed": False,
        },
        timeout_seconds=300,
        max_attempts=3,
        estimated_cost_usd=Decimal("0"),
        reserved_cost_usd=Decimal("0"),
        legacy_source={"phase": "P91", "runtime": "local_preview"},
    )


def test_candidates_are_retained_checked_selected_and_motion_gated(p89_database, p91_ready) -> None:
    service = ValidatedVisualProjectService(p89_database)
    review = VisualReviewService(p89_database)
    initialized = service.initialize(
        content_id=p91_ready["content_one"],
        request=project_request(p91_ready),
        actor=p91_ready["producer"],
    )
    assert initialized["created"] is True
    assert len(initialized["shots"]) >= 1
    assert len(initialized["candidates"]) == len(initialized["shots"]) * 3
    assert all(candidate["status"] == "queued" for candidate in initialized["candidates"])
    assert len({int(candidate["seed"]) for candidate in initialized["candidates"]}) == len(initialized["candidates"])
    assert all(float(candidate["actual_cost_usd"]) == 0 for candidate in initialized["candidates"])
    assert all(candidate["external_fee_incurred"] is False for candidate in initialized["candidates"])

    first_shot = initialized["shots"][0]
    first_version_candidates = [
        candidate for candidate in initialized["candidates"]
        if str(candidate["visual_shot_version_id"]) == str(first_shot["current_version_id"])
    ]
    failed_candidate_id = first_version_candidates[0]["id"]
    registered = register_all_candidates(
        p89_database,
        p91_ready,
        service,
        initialized,
        failed_candidate_id=failed_candidate_id,
    )
    failed = next(item for item in registered["candidates"] if str(item["id"]) == str(failed_candidate_id))
    assert failed["checks_status"] == "fail"
    assert len([check for check in registered["checks"] if str(check["visual_candidate_id"]) == str(failed["id"])]) == 10

    current_first_shot = next(item for item in registered["shots"] if str(item["id"]) == str(first_shot["id"]))
    with pytest.raises(psycopg.Error, match="all ten passing checks"):
        select_candidate(
            review,
            registered,
            shot=current_first_shot,
            candidate=failed,
            reviewer=p91_ready["reviewer"],
        )
    assert review.projects.detail(project_id=registered["project"]["id"])["candidate_decisions"] == []

    detail = review.projects.detail(project_id=registered["project"]["id"])
    for shot in detail["shots"]:
        candidates = [
            item for item in detail["candidates"]
            if str(item["visual_shot_version_id"]) == str(shot["current_version_id"])
            and item["checks_status"] == "pass"
        ]
        assert candidates
        detail = select_candidate(
            review,
            detail,
            shot=shot,
            candidate=candidates[0],
            reviewer=p91_ready["reviewer"],
        )

    assert all(shot["status"] == "approved" for shot in detail["shots"])
    assert all(shot["selected_candidate_id"] is not None for shot in detail["shots"])
    selected_candidate_id = detail["shots"][0]["selected_candidate_id"]

    with pytest.raises(psycopg.Error, match="continuity review passes"):
        GenerationJobService(p89_database).enqueue(
            preview_enqueue(p91_ready, detail, selected_candidate_id),
            actor=p91_ready["producer"],
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
            rationale="Every shot has a retained selected candidate with all ten checks and explicit reviewer evidence.",
        ),
        reviewer=p91_ready["reviewer"],
    )
    assert approved["project"]["status"] == "approved"

    job = GenerationJobService(p89_database).enqueue(
        preview_enqueue(p91_ready, approved, selected_candidate_id),
        actor=p91_ready["producer"],
    )
    assert job["job_type"] == "preview"
    assert float(job["estimated_cost_usd"]) == 0
    assert job["input_payload"]["visual_candidate_id"] == str(selected_candidate_id)


def test_prompt_revision_preserves_prior_candidates_and_jobs(p89_database, p91_ready) -> None:
    service = ValidatedVisualProjectService(p89_database)
    review = VisualReviewService(p89_database)
    initialized = service.initialize(
        content_id=p91_ready["content_one"],
        request=project_request(p91_ready, base_seed=930000),
        actor=p91_ready["producer"],
    )
    shot = initialized["shots"][0]
    old_version_id = shot["current_version_id"]
    old_candidates = [
        item for item in initialized["candidates"]
        if str(item["visual_shot_version_id"]) == str(old_version_id)
    ]
    assert len(old_candidates) == 3

    changed = review.decide_shot(
        project_id=initialized["project"]["id"],
        shot_id=shot["id"],
        shot_version_id=old_version_id,
        request=ShotDecisionRequest(
            expected_shot_lock_version=shot["lock_version"],
            decision=ShotDecision.CHANGES_REQUESTED,
            rationale="All candidates need a tighter landmark position and softer natural lighting.",
        ),
        reviewer=p91_ready["reviewer"],
    )
    changed_shot = next(item for item in changed["shots"] if str(item["id"]) == str(shot["id"]))
    revised = service.revise_shot(
        project_id=initialized["project"]["id"],
        shot_id=shot["id"],
        request=ShotRevisionRequest(
            expected_shot_lock_version=changed_shot["lock_version"],
            reason="Move the fan coral to the right third and soften the top light.",
            prompt_patch={
                "environment": {"landmark": "fan coral fixed on right third"},
                "lighting": {"direction": "soft diffused top light"},
            },
            negative_prompt_append="hard spotlight, moved landmark",
            base_seed=940000,
        ),
        actor=p91_ready["producer"],
    )
    revised_shot = next(item for item in revised["shots"] if str(item["id"]) == str(shot["id"]))
    assert str(revised_shot["current_version_id"]) != str(old_version_id)
    assert revised_shot["current_version"] == 2

    retained = [
        item for item in revised["candidates"]
        if str(item["visual_shot_version_id"]) == str(old_version_id)
    ]
    replacements = [
        item for item in revised["candidates"]
        if str(item["visual_shot_version_id"]) == str(revised_shot["current_version_id"])
    ]
    assert {str(item["id"]) for item in retained} == {str(item["id"]) for item in old_candidates}
    assert len(replacements) == 3
    assert not {str(item["generation_job_id"]) for item in retained}.intersection(
        {str(item["generation_job_id"]) for item in replacements}
    )
    assert not {int(item["seed"]) for item in retained}.intersection(
        {int(item["seed"]) for item in replacements}
    )
    assert "fan coral fixed on right third" in revised_shot["compiled_prompt"]
    assert "hard spotlight" in revised_shot["negative_prompt"]
