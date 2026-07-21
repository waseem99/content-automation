from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from src.application.generation_jobs.models import GenerationJobCompletion, GenerationJobType
from src.application.generation_jobs.service import GenerationJobService
from src.application.releases import FinalReleaseService
from src.application.releases.models import (
    AssemblyEnqueueRequest,
    AssemblyOutputRequest,
    FinalReleaseCreate,
    PlaybackReviewRequest,
    QaEvaluateRequest,
    ReleaseDecisionRequest,
    ReleaseInputApprovalRequest,
    ReleaseInputRequest,
)
from src.application.shared_storage.models import ArtifactVersionRequest
from src.application.shared_storage.service import _utcnow
from tests.integration.p96_release_support import (
    p89_database,
    p96_ready as p96_ready_fixture,
)
from tests.integration.test_p96_final_release_lifecycle import (
    passing_inspection,
    release_profile,
)


pytestmark = pytest.mark.integration


def create_shared_artifact(ready, *, key: str, kind: str, asset_key: str, days: int = 90):
    return ready["service"].create_artifact_version(
        request=ArtifactVersionRequest(
            brand_id=ready["brand_one"],
            portfolio_content_id=ready["content_one"],
            content_version=ready["content_one_version"],
            artifact_key=key,
            artifact_kind=kind,
            original_asset_id=ready["assets"][asset_key],
            backend_id=ready["shared_backend"]["id"],
            retention_until=_utcnow() + timedelta(days=days),
            metadata={"phase": "P97", "delivery_fixture": True},
        ),
        actor=ready["producer"],
    )["artifact"]


def approve_release_input(service, ready, artifact, role: str) -> None:
    service.decide_input(
        ReleaseInputApprovalRequest(
            artifact_version_id=artifact["id"],
            role=role,
            decision="approved",
            rationale=f"The exact {role} artifact is approved for the P97 release fixture.",
        ),
        actor=ready["reviewer"],
    )


def create_approved_release(database, ready) -> dict[str, object]:
    releases = FinalReleaseService(database)
    jobs = GenerationJobService(database)
    profile = releases.create_profile(release_profile(), actor=ready["admin"])["profile"]
    profile = releases.activate_profile(profile_id=profile["id"], actor=ready["admin"])["profile"]

    narration = create_shared_artifact(
        ready,
        key="p97/release/narration",
        kind="voiceover",
        asset_key="final_mix",
    )
    visual = create_shared_artifact(
        ready,
        key="p97/release/visual-001",
        kind="premium_clip",
        asset_key="visual",
    )
    thumbnail = create_shared_artifact(
        ready,
        key="p97/release/thumbnail",
        kind="thumbnail",
        asset_key="branding",
    )
    for artifact, role in (
        (narration, "narration"),
        (visual, "visual_shot"),
        (thumbnail, "branding"),
    ):
        approve_release_input(releases, ready, artifact, role)

    created = releases.create_release(
        FinalReleaseCreate(
            portfolio_content_id=ready["content_one"],
            content_version=ready["content_one_version"],
            render_profile_id=profile["id"],
            audio_mix_version_id=ready["audio_mix_version_id"],
            inputs=(
                ReleaseInputRequest(artifact_version_id=narration["id"], role="narration"),
                ReleaseInputRequest(
                    artifact_version_id=visual["id"],
                    role="visual_shot",
                    sequence_number=1,
                ),
                ReleaseInputRequest(artifact_version_id=thumbnail["id"], role="branding"),
            ),
            metadata={"release_label": "P97 approved delivery fixture"},
        ),
        actor=ready["producer"],
    )
    release_id = created["release"]["id"]
    releases.enqueue_assembly(
        release_id=release_id,
        request=AssemblyEnqueueRequest(
            preferred_worker_id=ready["producer"],
            max_attempts=2,
        ),
        actor=ready["producer"],
    )

    output = create_shared_artifact(
        ready,
        key="p97/release/final-output",
        kind="final_video",
        asset_key="output",
        days=180,
    )
    claimed = jobs.claim(
        worker_id=ready["producer"],
        allowed_brand_ids=(ready["brand_one"],),
        allowed_job_types=(GenerationJobType.ASSEMBLY,),
        requested_job_types=(GenerationJobType.ASSEMBLY,),
        providers=("local-assembly",),
    )
    assert claimed is not None
    jobs.complete(
        GenerationJobCompletion(
            job_id=claimed["job"]["id"],
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=ready["producer"],
            output_payload={
                "shared_artifact_version_id": str(output["id"]),
                "assembly_mode": "deterministic-release-assembler-v1",
            },
            provider_request_id="local-p97-release-fixture",
            actual_cost_usd=Decimal("0"),
        )
    )
    releases.register_assembly_output(
        release_id=release_id,
        request=AssemblyOutputRequest(
            output_artifact_version_id=output["id"],
            generation_job_id=claimed["job"]["id"],
        ),
        actor=ready["producer"],
    )
    with database.connection() as conn:
        output_hash = conn.execute(
            "SELECT sha256 FROM football_brief.assets WHERE id=%s",
            (output["original_asset_id"],),
        ).fetchone()["sha256"]
    passed = releases.evaluate_qa(
        release_id=release_id,
        request=QaEvaluateRequest(
            inspection=passing_inspection(output_hash),
            inspector_label="P97 delivery fixture probe",
        ),
        actor=ready["producer"],
    )
    submitted = releases.submit_playback_review(
        release_id=release_id,
        actor=ready["producer"],
    )
    releases.record_playback_review(
        release_id=release_id,
        request=PlaybackReviewRequest(
            decision="approved",
            checklist={
                "full_playback_completed": True,
                "narration_intelligible": True,
                "visual_order_correct": True,
                "captions_readable": True,
                "branding_correct": True,
                "disclosures_visible": True,
                "no_unintended_content": True,
            },
            rationale="The complete simulated-delivery release passed full playback review.",
        ),
        reviewer=ready["reviewer"],
    )
    approved = releases.decide_release(
        release_id=release_id,
        request=ReleaseDecisionRequest(
            decision="approved",
            rationale="The P97 fixture passed technical QA and complete playback review.",
            expected_lock_version=submitted["release"]["lock_version"],
        ),
        reviewer=ready["reviewer"],
    )
    assert passed["release"]["status"] == "qa_complete"
    assert approved["release"]["status"] == "approved"
    return {
        "release": approved["release"],
        "release_id": release_id,
        "thumbnail": thumbnail,
        "output": output,
        "profile": profile,
    }


@pytest.fixture()
def p97_ready(p89_database, tmp_path) -> dict[str, object]:
    ready = p96_ready_fixture.__wrapped__(p89_database, tmp_path)
    publisher = "publisher.delivery"
    outsider_publisher = "publisher.other"
    with p89_database.transaction() as conn:
        for operator_id, display_name, brand_id in (
            (publisher, "Delivery Publisher", ready["brand_one"]),
            (outsider_publisher, "Other Brand Publisher", ready["brand_two"]),
        ):
            user = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id,display_name,created_by)
                   VALUES (%s,%s,%s) RETURNING id""",
                (operator_id, display_name, ready["admin"]),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.operator_user_roles
                   (operator_user_id,role,assigned_by)
                   VALUES (%s,'publisher',%s)""",
                (user["id"], ready["admin"]),
            )
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id,brand_id,assigned_by)
                   VALUES (%s,%s,%s)""",
                (user["id"], brand_id, ready["admin"]),
            )
    approved_release = create_approved_release(p89_database, ready)
    return {
        **ready,
        **approved_release,
        "publisher": publisher,
        "outsider_publisher": outsider_publisher,
    }
