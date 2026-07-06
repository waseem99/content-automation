from __future__ import annotations

from src.domain.render_status import RenderJobStatus, RenderManifestStatus, RenderMode


def fail(code: str, message: str, severity: str = "block") -> dict:
    return {"code": code, "status": "fail", "severity": severity, "message": message}


def render_state_checks(job: dict, manifest) -> list[dict]:
    checks: list[dict] = []
    if job["status"] != RenderJobStatus.SUCCEEDED.value:
        checks.append(fail("RENDER_NOT_SUCCEEDED", "Render job has not succeeded"))
    if manifest.document.mode == RenderMode.PREVIEW:
        checks.append(fail("NOT_FOR_PUBLICATION", "Preview renders cannot be packaged"))
    if manifest.document.mode == RenderMode.PUBLISH and manifest.status != RenderManifestStatus.APPROVED:
        checks.append(fail("MANIFEST_NOT_APPROVED", "Publish manifest is not approved"))
    if manifest.document.mode == RenderMode.PUBLISH and job["output_asset_id"] is None:
        checks.append(fail("OUTPUT_ASSET_MISSING", "Publish render is missing an output asset"))
    return checks


def manifest_contract_checks(manifest) -> list[dict]:
    checks: list[dict] = []
    if manifest.document.mode != RenderMode.PUBLISH:
        return checks
    if manifest.document.not_for_publication:
        checks.append(fail("NOT_FOR_PUBLICATION", "Manifest is marked not for publication"))
    if manifest.document.watermark_text:
        checks.append(fail("PREVIEW_WATERMARK", "Publish manifest contains preview watermark text"))
    if any(asset.is_placeholder for asset in manifest.document.assets):
        checks.append(fail("PLACEHOLDER_ASSET", "Publish manifest contains placeholder assets"))
    return checks


def media_checks(inspection, preset) -> list[dict]:
    checks: list[dict] = []
    if inspection is None:
        return checks
    if not inspection.valid_container:
        checks.append(fail("OUTPUT_CORRUPTION", "Output container is invalid"))
    if inspection.width and inspection.height:
        if inspection.width != preset.width or inspection.height != preset.height:
            checks.append(fail("RESOLUTION_MISMATCH", "Output resolution does not match preset"))
    if inspection.fps is not None and abs(float(inspection.fps) - float(preset.fps)) > 0.25:
        checks.append(fail("FRAME_RATE_MISMATCH", "Output frame rate does not match preset"))
    if inspection.duration_sec is not None and inspection.duration_sec <= 0:
        checks.append(fail("DURATION_INVALID", "Output duration is invalid"))
    if inspection.black_frames_detected:
        checks.append(fail("BLACK_FRAMES_DETECTED", "Black frames detected"))
    if inspection.frozen_frames_detected:
        checks.append(fail("FROZEN_FRAMES_DETECTED", "Frozen frames detected"))
    if inspection.caption_clipping_detected:
        checks.append(fail("CAPTION_CLIPPING", "Caption clipping requires review", "human_review"))
    if inspection.safe_area_violation:
        checks.append(fail("SAFE_AREA_VIOLATION", "Safe-area issue requires review", "human_review"))
    if inspection.has_audio is False:
        checks.append(fail("AUDIO_MISSING", "No audio track detected", "human_review"))
    return checks
