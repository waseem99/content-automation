from __future__ import annotations

import shutil
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobEnqueue,
    GenerationJobType,
)
from src.application.generation_jobs.service import GenerationJobService
from src.application.production_workflow_service import ProductionWorkflowService
from src.application.scripts.models import (
    ClaimSourceDraft,
    ClaimSupportType,
    ScriptDecision,
    ScriptGenerateRequest,
    SourceDraft,
    SourceRightsDeclaration,
    SourceSupportUpdateRequest,
    SourceType,
)
from src.application.scripts.service import ScriptReviewService
from src.domain.production_workflow import ReviewDecision
from src.infrastructure.database.connection import Database
from src.operations.always_on_pipeline import AlwaysOnLocalPipelineService
from src.operations.local_worker_v2 import AlwaysOnLocalGenerationWorker
from tests.integration.test_p86_production_workflow_lifecycle import database, seeded

__all__ = ["database", "seeded"]
pytestmark = pytest.mark.integration


def _approve_concept_workflow(database: Database, seeded: dict[str, object]) -> dict[str, object]:
    workflow = ProductionWorkflowService(database)
    created = workflow.initialize(content_id=seeded["content_id"], actor=seeded["producer"])
    submitted = workflow.submit(
        workflow_id=created["workflow_id"],
        expected_lock_version=1,
        actor=seeded["producer"],
    )
    approved = workflow.decide(
        workflow_id=created["workflow_id"],
        expected_lock_version=submitted["workflow"]["lock_version"],
        reviewer=seeded["reviewer"],
        decision=ReviewDecision.APPROVED,
        rationale="Concept is approved for bounded local production",
    )
    assert approved["workflow"]["current_stage"] == "script_draft"
    return approved


def _approve_script(database: Database, seeded: dict[str, object]) -> UUID:
    _approve_concept_workflow(database, seeded)
    service = ScriptReviewService(database)
    initialized = service.initialize(
        content_id=seeded["content_id"],
        request=ScriptGenerateRequest(
            platform="facebook",
            format="vertical_short",
            language="en-US",
            target_duration_seconds=45,
            words_per_minute=150,
            duration_tolerance_percent=10,
            seed=104,
        ),
        actor=seeded["producer"],
    )
    document_id = initialized["document"]["id"]
    version_id = initialized["document"]["current_version_id"]
    claims = [
        claim for claim in initialized["claims"]
        if str(claim["script_version_id"]) == str(version_id)
    ]
    assert claims
    source = SourceDraft(
        source_key="p104-primary-source",
        source_type=SourceType.ACADEMIC,
        title="Reviewed evidence for the local production fixture",
        publisher="P104 Evidence Journal",
        canonical_url="https://example.org/p104/local-production-evidence",
        quality_score=95,
        rights_declaration=SourceRightsDeclaration.PUBLICLY_ACCESSIBLE,
        permitted_use="Factual verification and paraphrased educational explanation",
        evidence_digest="c" * 64,
        notes="The fixture copies no source wording or protected media.",
    )
    supported = service.update_source_support(
        document_id=document_id,
        request=SourceSupportUpdateRequest(
            expected_lock_version=1,
            sources=[source],
            claim_sources=[
                ClaimSourceDraft(
                    claim_key=claim["claim_key"],
                    source_key=source.source_key,
                    support_type=ClaimSupportType.DIRECT,
                    locator="Reviewed fixture evidence",
                    support_note="Directly supports this factual fixture claim for the integration proof.",
                )
                for claim in claims
            ],
            supported_claim_keys=[claim["claim_key"] for claim in claims],
        ),
        actor=seeded["producer"],
    )
    submitted = service.submit(
        document_id=document_id,
        expected_lock_version=supported["document"]["lock_version"],
        actor=seeded["producer"],
    )
    approved = service.decide(
        document_id=document_id,
        expected_lock_version=submitted["document"]["lock_version"],
        decision=ScriptDecision.APPROVED,
        rationale="Claims, sources, scene plan, timing, and wording are approved.",
        reviewer=seeded["reviewer"],
    )
    assert approved["document"]["current_version_status"] == "approved"
    return UUID(str(approved["document"]["current_version_id"]))


def test_bounded_script_batch_is_durable_zero_cost_and_idempotent(
    database: Database,
    seeded: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _approve_concept_workflow(database, seeded)
    monkeypatch.setenv("LOCAL_PRODUCER_OPERATOR_ID", str(seeded["producer"]))
    pipeline = AlwaysOnLocalPipelineService(database)
    first = pipeline.enqueue_scripts(
        limit=5,
        actor=str(seeded["producer"]),
        brand_ids=[seeded["brand_id"]],
    )
    assert first["ok"] is True, first
    assert len(first["enqueued"]) == 1
    assert first["enqueued"][0]["reused"] is False

    replay = pipeline.enqueue_scripts(
        limit=5,
        actor=str(seeded["producer"]),
        brand_ids=[seeded["brand_id"]],
    )
    assert len(replay["enqueued"]) == 1
    assert replay["enqueued"][0]["reused"] is True
    assert replay["enqueued"][0]["id"] == first["enqueued"][0]["id"]

    with database.connection() as conn:
        row = conn.execute(
            """SELECT job_type,status,provider,preferred_worker_id,
                      estimated_cost_usd,reserved_cost_usd,input_payload,legacy_source
               FROM football_brief.generation_jobs WHERE id=%s""",
            (first["enqueued"][0]["id"],),
        ).fetchone()
    assert row["job_type"] == "script"
    assert row["status"] == "queued"
    assert row["provider"] == "ollama-local"
    assert str(row["preferred_worker_id"]) == str(seeded["producer"])
    assert row["estimated_cost_usd"] == Decimal("0.000000")
    assert row["reserved_cost_usd"] == Decimal("0.000000")
    assert row["input_payload"]["request"]["adapter_mode"] == "local_model"
    assert row["legacy_source"]["bounded_batch"] is True

    status = pipeline.status(brand_ids=[seeded["brand_id"]])
    assert status["eligible"]["scripts"] == 1
    assert any(
        item["job_type"] == "script" and item["status"] == "queued" and item["count"] == 1
        for item in status["jobs"]
    )
    assert status["capabilities"]["managed_renderer"] is False
    assert status["capabilities"]["automatic_approval"] is False
    assert status["capabilities"]["live_publishing"] is False


def _complete_dependency(
    database: Database,
    *,
    seeded: dict[str, object],
    script_version_id: UUID,
    content_version: int,
    job_type: GenerationJobType,
    output_payload: dict[str, object],
) -> str:
    jobs = GenerationJobService(database)
    enqueued = jobs.enqueue(
        GenerationJobEnqueue(
            portfolio_content_id=seeded["content_id"],
            content_version=content_version,
            job_type=job_type,
            provider="fixture-local",
            model_id="fixture-model",
            preferred_worker_id=str(seeded["producer"]),
            idempotency_key=f"p104-fixture:{job_type.value}:{uuid4()}",
            input_payload={"fixture": True, "script_version_id": str(script_version_id)},
            timeout_seconds=120,
            max_attempts=1,
            estimated_cost_usd=Decimal("0"),
            reserved_cost_usd=Decimal("0"),
        ),
        actor=str(seeded["producer"]),
    )
    claimed = jobs.claim(
        worker_id=str(seeded["producer"]),
        allowed_brand_ids=[seeded["brand_id"]],
        allowed_job_types=[job_type],
        requested_job_types=[job_type],
        providers=["fixture-local"],
        lease_seconds=120,
    )
    assert claimed is not None
    jobs.complete(
        GenerationJobCompletion(
            job_id=claimed["job"]["id"],
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=str(seeded["producer"]),
            output_payload=output_payload,
            actual_cost_usd=0,
        )
    )
    return str(enqueued["id"])


def test_ffmpeg_preview_creates_reviewable_mp4_and_approved_local_asset(
    database: Database,
    seeded: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert shutil.which("ffmpeg"), "P104 CI must install FFmpeg"
    script_version_id = _approve_script(database, seeded)
    with database.connection() as conn:
        content_version = int(conn.execute(
            "SELECT version FROM football_brief.portfolio_content WHERE id=%s",
            (seeded["content_id"],),
        ).fetchone()["version"])

    artifact_root = tmp_path / "artifacts"
    source_root = artifact_root / "fixtures"
    source_root.mkdir(parents=True)
    wav_path = source_root / "narration.wav"
    png_path = source_root / "scene.png"
    samples = (0.08 * np.sin(2 * np.pi * 220 * np.arange(24000) / 24000)).astype(np.float32)
    sf.write(wav_path, samples, 24000, subtype="PCM_16")
    Image.new("RGB", (704, 1280), (24, 52, 76)).save(png_path)

    monkeypatch.setenv("LOCAL_PRODUCER_OPERATOR_ID", str(seeded["producer"]))
    monkeypatch.setenv("LOCAL_ARTIFACT_ROOT", str(artifact_root))
    monkeypatch.setenv("PORTFOLIO_MEDIA_ROOT", str(artifact_root))
    monkeypatch.setenv("LOCAL_FFMPEG_PATH", str(shutil.which("ffmpeg")))

    audio_job_id = _complete_dependency(
        database,
        seeded=seeded,
        script_version_id=script_version_id,
        content_version=content_version,
        job_type=GenerationJobType.NARRATION,
        output_payload={
            "kind": "local_kokoro_narration",
            "storage_path": str(wav_path),
            "storage_uri": "local-artifact://fixtures/narration.wav",
            "sha256": "a" * 64,
            "mime_type": "audio/wav",
            "size_bytes": wav_path.stat().st_size,
            "provider": "fixture-local",
            "model_id": "fixture-audio",
        },
    )
    image_job_id = _complete_dependency(
        database,
        seeded=seeded,
        script_version_id=script_version_id,
        content_version=content_version,
        job_type=GenerationJobType.KEYFRAME,
        output_payload={
            "kind": "local_comfyui_keyframe",
            "storage_path": str(png_path),
            "storage_uri": "local-artifact://fixtures/scene.png",
            "sha256": "b" * 64,
            "mime_type": "image/png",
            "size_bytes": png_path.stat().st_size,
            "provider": "fixture-local",
            "model_id": "fixture-image",
        },
    )

    worker = AlwaysOnLocalGenerationWorker(database, allowed_job_types=[GenerationJobType.PREVIEW])
    preview_job = {
        "id": uuid4(),
        "portfolio_content_id": seeded["content_id"],
        "content_version": content_version,
        "model_id": "ffmpeg-slideshow-v1",
        "timeout_seconds": 180,
        "input_payload": {
            "script_version_id": str(script_version_id),
            "audio_job_ids": [audio_job_id],
            "scenes": [
                {"sequence": 1, "generation_job_id": image_job_id, "duration_seconds": 1.0}
            ],
            "width": 704,
            "height": 1280,
            "fps": 30,
        },
    }
    output = worker._preview(preview_job)
    preview_path = Path(output["storage_path"])
    assert preview_path.is_file()
    assert preview_path.stat().st_size > 0
    assert output["mime_type"] == "video/mp4"
    assert output["external_fee_incurred"] is False
    assert output["automatic_approval"] is False

    worker._register_preview(job=preview_job, output=output)
    with database.connection() as conn:
        asset = conn.execute(
            "SELECT asset_type,lifecycle_status FROM football_brief.assets WHERE sha256=%s",
            (output["sha256"],),
        ).fetchone()
        artifact = conn.execute(
            """SELECT kind,review_status,local_locator,mime_type
               FROM football_brief.portfolio_content_artifacts
               WHERE portfolio_content_id=%s AND local_locator=%s""",
            (seeded["content_id"], output["local_locator"]),
        ).fetchone()
    assert asset["asset_type"] == "video"
    assert asset["lifecycle_status"] == "approved"
    assert artifact["kind"] == "preview"
    assert artifact["review_status"] == "pending"
    assert artifact["mime_type"] == "video/mp4"
