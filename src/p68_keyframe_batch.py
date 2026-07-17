"""Work orders and provenance-aware intake for P68 shot keyframes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from src.p68_job_state import atomic_write_json, utc_now
from src.p68_pilot_batch import EXPECTED_PILOT_IDS
from src.p68_scientific_animation import RENDERERS


WORK_ORDER_VERSION = "p68.keyframe_work_orders.v1"
PROVENANCE_VERSION = "p68.keyframe_provenance.v1"
DESIGNATION_VERSION = "p68.shot_keyframe_designations.v1"
SOURCE_KINDS = {"generated_original", "commissioned_original", "licensed_asset"}


def _load(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.is_file():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_keyframe_work_orders(pilots_root: str | Path, artifact_root: str | Path) -> dict[str, Any]:
    pilots = []
    total, approved, awaiting = 0, 0, 0
    for plan_path in sorted(Path(pilots_root).glob("*/content-plan.json")):
        plan = _load(plan_path)
        pilot_id = str(plan["pilot_id"])
        prompts = {item["shot_id"]: item for item in _load(plan_path.parent / "clip-prompts.json")}
        artifact_dir = Path(artifact_root) / "gold" / pilot_id
        provenance = _load(artifact_dir / "generated-assets" / "keyframe-provenance.json", {"shots": {}})
        designations = _load(artifact_dir / "generated-assets" / "shot-keyframes.json", {"shots": {}})
        orders = []
        for shot in plan.get("shots") or []:
            shot_id = str(shot["shot_id"])
            if (pilot_id, shot_id) in RENDERERS:
                continue
            total += 1
            designation = (designations.get("shots") or {}).get(shot_id) or {}
            asset = (provenance.get("shots") or {}).get(shot_id) or {}
            is_approved = bool(
                designation.get("approved_for_generation")
                and asset.get("human_review_status") == "approved_for_generation"
            )
            approved += int(is_approved)
            awaiting += int(not is_approved)
            prompt = prompts[shot_id]
            orders.append(
                {
                    "pilot_id": pilot_id,
                    "shot_id": shot_id,
                    "story_stage": shot.get("story_stage"),
                    "target": {"orientation": "portrait", "aspect_ratio": "9:16", "minimum_width": 704, "minimum_height": 1280},
                    "visual_action": shot.get("visual_action"),
                    "camera": shot.get("camera"),
                    "entry_action": shot.get("entry_action"),
                    "exit_action": shot.get("exit_action"),
                    "continuity_bible": plan.get("continuity_bible"),
                    "still_image_prompt": (
                        f"Original vertical cinematic keyframe at the start of this shot. {shot.get('visual_action')}. "
                        f"Subject lock: {plan['continuity_bible']['subject_identity']}. "
                        f"Environment lock: {plan['continuity_bible']['environment']}. "
                        f"Lighting: {plan['continuity_bible']['lighting']}. "
                        f"Color treatment: {plan['continuity_bible']['color_treatment']}. "
                        f"Camera: {shot.get('camera')}. Screen direction: {shot.get('screen_direction')}. "
                        "Natural anatomy and physically plausible composition; no text, logo, watermark, border, or collage."
                    ),
                    "negative_prompt": prompt.get("negative_prompt"),
                    "asset_path": asset.get("normalized_path"),
                    "human_review_status": asset.get("human_review_status") or "asset_required",
                    "ready_for_video_generation": is_approved,
                    "production_candidate": False,
                    "publish_allowed": False,
                }
            )
        pilots.append({"pilot_id": pilot_id, "brand_profile": plan.get("brand_profile"), "orders": orders})
    return {
        "schema_version": WORK_ORDER_VERSION,
        "pilot_count": len(pilots),
        "roster_complete": {item["pilot_id"] for item in pilots} == EXPECTED_PILOT_IDS,
        "pilots": pilots,
        "natural_motion_keyframes_required": total,
        "approved_keyframes": approved,
        "keyframes_awaiting_asset_or_review": awaiting,
        "all_keyframes_ready": bool(total and approved == total),
        "generation_calls_made": 0,
        "paid_provider_calls_made": 0,
        "vercel_deployment_required": False,
        "publish_allowed": False,
    }


def inspect_image(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with Image.open(path) as image:
        width, height = image.size
        image.verify()
    ratio = width / height
    errors = []
    if width < 704 or height < 1280:
        errors.append("minimum_dimensions_704x1280_required")
    if width >= height:
        errors.append("portrait_orientation_required")
    if not 0.54 <= ratio <= 0.59:
        errors.append("aspect_ratio_must_be_close_to_9_16")
    return {"width": width, "height": height, "aspect_ratio": round(ratio, 5), "errors": errors, "passed": not errors}


def intake_keyframe(
    *,
    pilots_root: str | Path,
    artifact_root: str | Path,
    pilot_id: str,
    shot_id: str,
    source_path: str | Path,
    source_kind: str,
    provider: str,
    model_or_collection: str,
    rights_evidence: str,
) -> dict[str, Any]:
    if source_kind not in SOURCE_KINDS:
        raise ValueError(f"source_kind must be one of: {', '.join(sorted(SOURCE_KINDS))}")
    if not provider.strip() or not model_or_collection.strip() or not rights_evidence.strip():
        raise ValueError("provider, model_or_collection, and rights_evidence are required")
    plan_path = Path(pilots_root) / pilot_id / "content-plan.json"
    plan = _load(plan_path)
    shot_ids = {str(item["shot_id"]) for item in plan.get("shots") or []}
    if shot_id not in shot_ids:
        raise ValueError(f"Unknown shot {pilot_id}/{shot_id}")
    if (pilot_id, shot_id) in RENDERERS:
        raise ValueError(f"{pilot_id}/{shot_id} is routed to deterministic authored animation")
    source = Path(source_path)
    probe = inspect_image(source)
    if not probe["passed"]:
        raise ValueError(f"Keyframe image failed validation: {', '.join(probe['errors'])}")

    asset_root = Path(artifact_root) / "gold" / pilot_id / "generated-assets"
    asset_root.mkdir(parents=True, exist_ok=True)
    versions = sorted(asset_root.glob(f"{shot_id.lower()}-keyframe-v*.png"))
    target = asset_root / f"{shot_id.lower()}-keyframe-v{len(versions) + 1}.png"
    partial = target.with_suffix(".partial.png")
    with Image.open(source) as image:
        image.convert("RGB").save(partial, format="PNG", optimize=True)
    partial.replace(target)
    record = {
        "shot_id": shot_id,
        "source_kind": source_kind,
        "provider": provider.strip(),
        "model_or_collection": model_or_collection.strip(),
        "rights_evidence": rights_evidence.strip(),
        "source_sha256": _sha256(source),
        "normalized_path": str(target),
        "normalized_sha256": _sha256(target),
        "image_probe": inspect_image(target),
        "ingested_at": utc_now(),
        "human_review_status": "pending_keyframe_review",
        "approved_for_generation": False,
        "production_candidate": False,
        "publish_allowed": False,
    }
    provenance_path = asset_root / "keyframe-provenance.json"
    provenance = _load(provenance_path, {"schema_version": PROVENANCE_VERSION, "pilot_id": pilot_id, "shots": {}})
    provenance.setdefault("shots", {})[shot_id] = record
    provenance["publish_allowed"] = False
    atomic_write_json(provenance_path, provenance)
    return {**record, "provenance_path": str(provenance_path)}


def approve_keyframe(
    *, artifact_root: str | Path, pilot_id: str, shot_id: str, reviewer: str, note: str
) -> dict[str, Any]:
    if not reviewer.strip() or not note.strip():
        raise ValueError("reviewer and approval note are required")
    asset_root = Path(artifact_root) / "gold" / pilot_id / "generated-assets"
    provenance_path = asset_root / "keyframe-provenance.json"
    provenance = _load(provenance_path)
    record = (provenance.get("shots") or {}).get(shot_id)
    if not record:
        raise ValueError(f"No ingested keyframe for {pilot_id}/{shot_id}")
    path = Path(str(record["normalized_path"]))
    if not path.is_file() or _sha256(path) != record.get("normalized_sha256"):
        raise ValueError("Keyframe file is missing or changed after intake")
    record.update(
        {
            "human_review_status": "approved_for_generation",
            "approved_for_generation": True,
            "reviewer": reviewer.strip(),
            "approval_note": note.strip(),
            "approved_at": utc_now(),
            "publish_allowed": False,
        }
    )
    atomic_write_json(provenance_path, provenance)
    designation_path = asset_root / "shot-keyframes.json"
    designations = _load(designation_path, {"schema_version": DESIGNATION_VERSION, "shots": {}})
    designations.setdefault("shots", {})[shot_id] = {
        "path": path.name,
        "approved_for_generation": True,
        "reason": note.strip(),
        "reviewer": reviewer.strip(),
        "provenance_sha256": record["normalized_sha256"],
        "publish_allowed": False,
    }
    atomic_write_json(designation_path, designations)
    return {**record, "designation_path": str(designation_path)}


def write_keyframe_work_orders(pilots_root: str | Path, artifact_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    result = build_keyframe_work_orders(pilots_root, artifact_root)
    atomic_write_json(Path(output_path), result)
    return result
