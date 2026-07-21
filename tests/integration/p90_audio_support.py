from __future__ import annotations

import hashlib
from uuid import UUID

import pytest

from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobType,
)
from src.application.generation_jobs.service import GenerationJobService
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
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def script_request() -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        platform="facebook",
        format="vertical_short",
        language="en-US",
        target_duration_seconds=60,
        words_per_minute=150,
        duration_tolerance_percent=10,
        seed=901,
    )


def source_support(expected_lock: int) -> SourceSupportUpdateRequest:
    source = SourceDraft(
        source_key="source-p90",
        source_type=SourceType.ACADEMIC,
        title="Evidence for the approved local narration script",
        publisher="Evidence Journal",
        canonical_url="https://example.org/evidence/p90",
        quality_score=95,
        rights_declaration=SourceRightsDeclaration.PUBLICLY_ACCESSIBLE,
        permitted_use="Factual verification and paraphrase",
        evidence_digest="9" * 64,
        notes="Text is paraphrased; no source media enters the audio pipeline.",
    )
    return SourceSupportUpdateRequest(
        expected_lock_version=expected_lock,
        sources=[source],
        claim_sources=[
            ClaimSourceDraft(
                claim_key="claim-hook",
                source_key=source.source_key,
                support_type=ClaimSupportType.CORROBORATING,
                locator="Findings",
                support_note="Supports the factual opening.",
            ),
            ClaimSourceDraft(
                claim_key="claim-body",
                source_key=source.source_key,
                support_type=ClaimSupportType.DIRECT,
                locator="Methods and findings",
                support_note="Supports the central mechanism.",
            ),
        ],
        supported_claim_keys=["claim-hook", "claim-body"],
    )


def pin_matching_legacy_preset(database, *, content_id: UUID, preset_id: UUID) -> None:
    """Complete a legacy profile-only pin without permitting profile replacement."""

    with database.transaction() as conn:
        updated = conn.execute(
            """UPDATE football_brief.portfolio_content pc
               SET narration_preset_id=%s
               FROM football_brief.brand_narration_presets bnp
               WHERE pc.id=%s
                 AND bnp.id=%s
                 AND pc.brand_profile_id=bnp.brand_profile_id
                 AND pc.narration_preset_id IS NULL
               RETURNING pc.id""",
            (preset_id, content_id, preset_id),
        ).fetchone()
    assert updated is not None


@pytest.fixture()
def p90_ready(p89_database, p89_seeded) -> dict[str, object]:
    with p89_database.connection() as conn:
        preset = conn.execute(
            """SELECT bnp.id, bnp.approved_voice_id
               FROM football_brief.brand_narration_presets bnp
               WHERE bnp.brand_profile_id=%s AND bnp.is_default=true""",
            (p89_seeded["profile_one"],),
        ).fetchone()
    pin_matching_legacy_preset(
        p89_database,
        content_id=p89_seeded["content_one"],
        preset_id=preset["id"],
    )

    scripts = ScriptReviewService(p89_database)
    initialized = scripts.initialize(
        content_id=p89_seeded["content_one"],
        request=script_request(),
        actor=p89_seeded["producer"],
    )
    document_id = initialized["document"]["id"]
    supported = scripts.update_source_support(
        document_id=document_id,
        request=source_support(expected_lock=1),
        actor=p89_seeded["producer"],
    )
    submitted = scripts.submit(
        document_id=document_id,
        expected_lock_version=supported["document"]["lock_version"],
        actor=p89_seeded["producer"],
    )
    approved = scripts.decide(
        document_id=document_id,
        expected_lock_version=submitted["document"]["lock_version"],
        decision=ScriptDecision.APPROVED,
        rationale="Claims, sources, scenes, wording, and duration are approved for local narration.",
        reviewer=p89_seeded["reviewer"],
    )
    return {
        **p89_seeded,
        "preset_id": preset["id"],
        "voice_id": preset["approved_voice_id"],
        "script_document_id": document_id,
        "script_version_id": approved["document"]["current_version_id"],
    }


def register_audio_asset(database, *, key: str, created_by: str) -> UUID:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    with database.transaction() as conn:
        row = conn.execute(
            """INSERT INTO football_brief.assets
               (asset_type, source_type, lifecycle_status, original_filename,
                storage_uri, sha256, mime_type, size_bytes, metadata, created_by)
               VALUES ('audio','ai_generated','approved',%s,%s,%s,'audio/wav',1024,
                       %s::jsonb,%s)
               RETURNING id""",
            (
                f"{key}.wav",
                f"file:///tmp/p90/{key}.wav",
                digest,
                '{"phase":"P90","local":true}',
                created_by,
            ),
        ).fetchone()
    return row["id"]


def register_music_without_rights(database, *, key: str, created_by: str) -> UUID:
    return register_audio_asset(database, key=key, created_by=created_by)


def complete_next_narration_job(
    database,
    *,
    worker: str,
    brand_id: UUID,
) -> dict:
    jobs = GenerationJobService(database)
    claimed = jobs.claim(
        worker_id=worker,
        allowed_brand_ids=[brand_id],
        allowed_job_types=[GenerationJobType.NARRATION],
        requested_job_types=[GenerationJobType.NARRATION],
        providers=["kokoro-onnx"],
        lease_seconds=120,
    )
    assert claimed is not None
    completed = jobs.complete(
        GenerationJobCompletion(
            job_id=claimed["job"]["id"],
            attempt_id=claimed["attempt"]["id"],
            lease_token=claimed["lease_token"],
            worker_id=worker,
            output_payload={
                "local": True,
                "provider": "kokoro-onnx",
                "audio_uri": f"file:///tmp/p90/{claimed['job']['id']}.wav",
                "external_fee_incurred": False,
            },
            actual_cost_usd=0,
        )
    )
    assert completed["job"]["actual_cost_usd"] == 0
    return claimed["job"]
