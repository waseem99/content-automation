from __future__ import annotations

import hashlib
from uuid import UUID

import pytest

from src.application.generation_jobs.models import GenerationJobCompletion, GenerationJobType
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
from src.application.visuals.models import (
    CandidateCheck,
    CandidateCheckStatus,
    CandidateCheckType,
    ContinuityReferenceRequest,
    VisualPresetRequest,
    VisualProjectInitializeRequest,
)
from src.application.visuals.preset_service import VisualPresetService
from tests.integration.p89_script_support import p89_database, p89_seeded


pytestmark = pytest.mark.integration


def approved_script_request() -> ScriptGenerateRequest:
    return ScriptGenerateRequest(
        platform="facebook",
        format="vertical_short",
        language="en-US",
        target_duration_seconds=60,
        words_per_minute=150,
        duration_tolerance_percent=10,
        seed=911,
    )


def source_support(expected_lock: int) -> SourceSupportUpdateRequest:
    source = SourceDraft(
        source_key="source-p91",
        source_type=SourceType.ACADEMIC,
        title="Evidence for approved visual scene planning",
        publisher="Visual Evidence Journal",
        canonical_url="https://example.org/evidence/p91",
        quality_score=96,
        rights_declaration=SourceRightsDeclaration.PUBLICLY_ACCESSIBLE,
        permitted_use="Factual verification and paraphrase",
        evidence_digest="8" * 64,
        notes="No source media is copied into local candidate generation.",
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
                support_note="Supports the central mechanism and approved scenes.",
            ),
        ],
        supported_claim_keys=["claim-hook", "claim-body"],
    )


def visual_preset_request() -> VisualPresetRequest:
    return VisualPresetRequest(
        preset_key="marine-science",
        display_name="Marine Science Portrait",
        palette={"primary": "deep ocean blue", "accent": "warm coral", "neutral": "sand"},
        subject_rules={
            "species": "scientifically plausible red-brown octopus",
            "identity_marker": "one pale crescent mark on the second left arm",
        },
        environment_rules={
            "location": "clear shallow reef",
            "landmarks": ["textured volcanic rock", "fan coral on frame right"],
        },
        camera_rules={"lens": "35mm", "perspective": "natural eye level", "motion": "locked keyframe"},
        lighting_rules={"direction": "soft top light", "time": "late morning", "contrast": "natural"},
        framing_rules={"orientation": "portrait", "safe_area": "upper and lower caption margins"},
        negative_prompt="illustration, cartoon, fantasy anatomy, extra arms",
        exclusions=["brand logos", "embedded text", "watermarks", "UI overlays"],
    )


@pytest.fixture()
def p91_ready(p89_database, p89_seeded) -> dict[str, object]:
    scripts = ScriptReviewService(p89_database)
    initialized = scripts.initialize(
        content_id=p89_seeded["content_one"],
        request=approved_script_request(),
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
        rationale="Claims, sources, wording, duration, and scene plan are approved for local candidate generation.",
        reviewer=p89_seeded["reviewer"],
    )

    presets = VisualPresetService(p89_database)
    created = presets.create(
        brand_profile_id=p89_seeded["profile_one"],
        request=visual_preset_request(),
        actor=p89_seeded["admin"],
    )
    activated = presets.activate(
        preset_id=created["preset"]["id"],
        actor=p89_seeded["admin"],
    )
    reference_asset_id = register_image_asset(
        p89_database,
        key="p91-octopus-continuity-reference",
        created_by=p89_seeded["producer"],
    )
    return {
        **p89_seeded,
        "script_document_id": document_id,
        "script_version_id": approved["document"]["current_version_id"],
        "visual_preset_id": activated["preset"]["id"],
        "reference_asset_id": reference_asset_id,
    }


def project_request(ready: dict[str, object], *, base_seed: int = 910000) -> VisualProjectInitializeRequest:
    return VisualProjectInitializeRequest(
        visual_preset_id=ready["visual_preset_id"],
        provider="comfyui-sdxl-local",
        model_id="sdxl-base-1.0",
        candidate_count=3,
        width=704,
        height=1280,
        base_seed=base_seed,
        continuity_references=[
            ContinuityReferenceRequest(
                reference_key="octopus-subject",
                reference_type="subject",
                asset_id=ready["reference_asset_id"],
                reference_fingerprint="a" * 64,
                description="Same red-brown octopus with one pale crescent arm mark.",
                attributes={"identity_marker": "pale crescent on second left arm"},
            ),
            ContinuityReferenceRequest(
                reference_key="reef-landmark",
                reference_type="landmark",
                reference_fingerprint="b" * 64,
                description="Textured volcanic rock with fan coral on frame right.",
                attributes={"screen_position": "right third"},
            ),
        ],
    )


def register_image_asset(database, *, key: str, created_by: str) -> UUID:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    with database.transaction() as conn:
        row = conn.execute(
            """INSERT INTO football_brief.assets
               (asset_type,source_type,lifecycle_status,original_filename,
                storage_uri,sha256,mime_type,size_bytes,metadata,created_by)
               VALUES ('image','ai_generated','approved',%s,%s,%s,'image/png',2048,
                       %s::jsonb,%s) RETURNING id""",
            (
                f"{key}.png",
                f"file:///tmp/p91/{key}.png",
                digest,
                '{"phase":"P91","local":true}',
                created_by,
            ),
        ).fetchone()
    return row["id"]


def complete_next_keyframe_job(database, *, worker: str, brand_id: UUID) -> dict:
    jobs = GenerationJobService(database)
    claimed = jobs.claim(
        worker_id=worker,
        allowed_brand_ids=[brand_id],
        allowed_job_types=[GenerationJobType.KEYFRAME],
        requested_job_types=[GenerationJobType.KEYFRAME],
        providers=["comfyui-sdxl-local"],
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
                "provider": "comfyui-sdxl-local",
                "image_uri": f"file:///tmp/p91/{claimed['job']['id']}.png",
                "external_fee_incurred": False,
            },
            actual_cost_usd=0,
        )
    )
    assert float(completed["job"]["actual_cost_usd"]) == 0
    return claimed["job"]


def candidate_checks(*, failed_check: CandidateCheckType | None = None) -> list[CandidateCheck]:
    return [
        CandidateCheck(
            check_type=kind,
            status=(CandidateCheckStatus.FAIL if kind == failed_check else CandidateCheckStatus.PASS),
            score=(35 if kind == failed_check else 100),
            evidence={
                "local_checker": True,
                "check": kind.value,
                "continuity_reference_used": kind.value.endswith("consistency"),
            },
            checked_by="p91-local-checker",
        )
        for kind in CandidateCheckType
    ]
