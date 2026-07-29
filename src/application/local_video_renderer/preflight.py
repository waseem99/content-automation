from __future__ import annotations

import hashlib
import json
from typing import Any

from src.application.local_video_renderer.models import LocalVideoPreflightRequest
from src.application.video_pilot.models import DistributionScope, ModelUsePreflightRequest
from src.application.video_pilot.policy import evaluate_model_policy


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def evaluate_local_video_preflight(
    *,
    request: LocalVideoPreflightRequest,
    manifest: dict[str, Any],
    acknowledgement: dict[str, Any],
    model_policy: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []

    if manifest.get("status") != "active":
        reasons.append("workflow_manifest_not_active")
    if acknowledgement.get("license_acknowledged") is not True:
        reasons.append("model_license_not_acknowledged")
    if request.workflow_sha256 != str(manifest.get("workflow_sha256")):
        reasons.append("workflow_hash_mismatch")
    if request.checkpoint_sha256 != str(manifest.get("expected_checkpoint_sha256")):
        reasons.append("checkpoint_hash_mismatch")
    if request.checkpoint_sha256 != str(acknowledgement.get("checkpoint_sha256")):
        reasons.append("acknowledged_checkpoint_hash_mismatch")
    if str(manifest.get("model_acknowledgement_id")) != str(acknowledgement.get("id")):
        reasons.append("workflow_model_acknowledgement_mismatch")
    if str(acknowledgement.get("model_policy_id")) != str(model_policy.get("id")):
        reasons.append("model_policy_binding_mismatch")

    if request.width not in {int(v) for v in manifest.get("supported_widths") or ()}:
        reasons.append("unsupported_width")
    if request.height not in {int(v) for v in manifest.get("supported_heights") or ()}:
        reasons.append("unsupported_height")
    if request.fps not in {int(v) for v in manifest.get("supported_fps") or ()}:
        reasons.append("unsupported_fps")
    if not int(manifest.get("min_frames", 0)) <= request.frame_count <= int(manifest.get("max_frames", 0)):
        reasons.append("unsupported_frame_count")
    if not int(manifest.get("min_steps", 0)) <= request.inference_steps <= int(manifest.get("max_steps", 0)):
        reasons.append("unsupported_inference_steps")

    model_result = evaluate_model_policy(
        model_policy,
        ModelUsePreflightRequest(
            provider_key=str(model_policy["provider_key"]),
            model_key=str(model_policy["model_key"]),
            distribution_scope=DistributionScope(request.distribution_scope),
            release_territories=request.release_territories,
        ),
    )
    reasons.extend(str(value) for value in model_result["rejection_reasons"])

    fingerprint_document = {
        "portfolio_content_id": str(request.portfolio_content_id),
        "content_version": request.content_version,
        "pilot_case_id": str(request.pilot_case_id) if request.pilot_case_id else None,
        "workflow_manifest_id": str(manifest.get("id")),
        "workflow_sha256": request.workflow_sha256,
        "checkpoint_sha256": request.checkpoint_sha256,
        "model_policy_id": str(model_policy.get("id")),
        "distribution_scope": request.distribution_scope,
        "release_territories": list(request.release_territories),
        "width": request.width,
        "height": request.height,
        "fps": request.fps,
        "frame_count": request.frame_count,
        "inference_steps": request.inference_steps,
        "seed": request.seed,
        "prompt": request.prompt,
        "negative_prompt": request.negative_prompt,
        "input_asset_ids": [str(value) for value in request.input_asset_ids],
        "request_metadata": request.request_metadata,
    }

    return {
        "ok": True,
        "kind": "local_video_renderer_preflight",
        "accepted": not reasons,
        "rejection_reasons": sorted(set(reasons)),
        "request_fingerprint": _fingerprint(fingerprint_document),
        "external_fee_possible": False,
        "workflow_manifest_id": str(manifest.get("id")),
        "model_policy_id": str(model_policy.get("id")),
        "model_use_preflight": model_result,
    }
