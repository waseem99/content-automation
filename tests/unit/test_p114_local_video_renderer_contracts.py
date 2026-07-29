from __future__ import annotations

from uuid import UUID

from src.application.local_video_renderer.models import LocalVideoPreflightRequest
from src.application.local_video_renderer.preflight import evaluate_local_video_preflight


def request(**overrides):
    value = {
        "portfolio_content_id": UUID("00000000-0000-0000-0000-000000000001"),
        "content_version": 1,
        "workflow_key": "wan22-draft-i2v",
        "workflow_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "distribution_scope": "global_public",
        "release_territories": (),
        "width": 1280,
        "height": 720,
        "fps": 24,
        "frame_count": 81,
        "inference_steps": 8,
        "seed": 42,
        "prompt": "A restrained cinematic camera move around the approved keyframe.",
        "input_asset_ids": (UUID("00000000-0000-0000-0000-000000000002"),),
    }
    value.update(overrides)
    return LocalVideoPreflightRequest(**value)


def fixtures():
    policy_id = UUID("00000000-0000-0000-0000-000000000010")
    acknowledgement_id = UUID("00000000-0000-0000-0000-000000000020")
    policy = {
        "id": policy_id,
        "provider_key": "wan-ai",
        "model_key": "Wan2.2-TI2V-5B",
        "version": 1,
        "evidence_digest": "c" * 64,
        "commercial_use_allowed": True,
        "allowed_use_scopes": ["internal", "territory_limited", "global_public"],
        "allowed_territories": ["worldwide"],
        "prohibited_territories": [],
        "requires_written_clearance": False,
    }
    acknowledgement = {
        "id": acknowledgement_id,
        "model_policy_id": policy_id,
        "checkpoint_sha256": "b" * 64,
        "license_acknowledged": True,
    }
    manifest = {
        "id": UUID("00000000-0000-0000-0000-000000000030"),
        "status": "active",
        "model_acknowledgement_id": acknowledgement_id,
        "workflow_sha256": "a" * 64,
        "expected_checkpoint_sha256": "b" * 64,
        "supported_widths": [1280],
        "supported_heights": [720],
        "supported_fps": [24],
        "min_frames": 49,
        "max_frames": 145,
        "min_steps": 4,
        "max_steps": 20,
    }
    return manifest, acknowledgement, policy


def test_wan_global_public_preflight_accepts_exact_acknowledged_hashes() -> None:
    manifest, acknowledgement, policy = fixtures()
    result = evaluate_local_video_preflight(
        request=request(),
        manifest=manifest,
        acknowledgement=acknowledgement,
        model_policy=policy,
    )
    assert result["accepted"] is True
    assert result["external_fee_possible"] is False
    assert len(result["request_fingerprint"]) == 64


def test_preflight_fails_closed_on_hash_or_license_mismatch() -> None:
    manifest, acknowledgement, policy = fixtures()
    acknowledgement["license_acknowledged"] = False
    result = evaluate_local_video_preflight(
        request=request(workflow_sha256="d" * 64),
        manifest=manifest,
        acknowledgement=acknowledgement,
        model_policy=policy,
    )
    assert result["accepted"] is False
    assert "workflow_hash_mismatch" in result["rejection_reasons"]
    assert "model_license_not_acknowledged" in result["rejection_reasons"]


def test_hunyuan_global_public_remains_blocked_by_model_policy() -> None:
    manifest, acknowledgement, policy = fixtures()
    policy.update(
        {
            "provider_key": "tencent-hunyuan",
            "model_key": "HunyuanVideo-1.5-480p-I2V-Step-Distilled",
            "allowed_use_scopes": ["internal", "territory_limited"],
            "allowed_territories": ["Pakistan"],
            "prohibited_territories": ["European Union", "United Kingdom", "South Korea"],
            "requires_written_clearance": True,
        }
    )
    result = evaluate_local_video_preflight(
        request=request(),
        manifest=manifest,
        acknowledgement=acknowledgement,
        model_policy=policy,
    )
    assert result["accepted"] is False
    assert "distribution_scope_not_allowed" in result["rejection_reasons"]
    assert "global_public_distribution_reaches_prohibited_territories" in result["rejection_reasons"]
