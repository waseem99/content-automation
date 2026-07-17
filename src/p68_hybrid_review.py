"""Assemble hybrid P68 reviews from natural-video and authored-science clips."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.p68_clip_stitcher import assemble_clip_plan
from src.p68_job_state import atomic_write_json
from src.p68_production_pipeline import automated_quality, select_narration


HYBRID_VERSION = "p68.hybrid_review.v1"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_clip_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"clips": []}
    payload = _load(path)
    payload.setdefault("clips", [])
    return payload


def _latest_science_manifest(artifact_dir: Path) -> Path:
    paths = sorted((artifact_dir / "clips").glob("scientific-v*/scientific-animation-manifest.json"))
    if not paths:
        raise FileNotFoundError(f"No scientific animation manifest exists under {artifact_dir / 'clips'}")
    return paths[-1]


def build_hybrid_manifest(
    plan: dict[str, Any],
    natural_manifest: dict[str, Any],
    science_manifest: dict[str, Any],
    selection_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    natural = {item["shot_id"]: item for item in natural_manifest.get("clips", [])}
    science = {item["shot_id"]: item for item in science_manifest.get("clips", [])}
    selected = {
        item["shot_id"]: item
        for item in (selection_manifest or {}).get("selected_clips", [])
    }
    clips = []
    for shot in plan["shots"]:
        shot_id = shot["shot_id"]
        clip = dict(science.get(shot_id) or selected.get(shot_id) or natural.get(shot_id) or {})
        if not clip:
            raise ValueError(f"No clip is available for {shot_id}")
        clip["shot_id"] = shot_id
        clips.append(clip)
    preview_fallbacks = [item["shot_id"] for item in clips if item.get("preview_only")]
    pending_review = [
        item["shot_id"]
        for item in clips
        if item.get("human_review_status") != "approved_for_assembly" or not item.get("quality_approved")
    ]
    return {
        "schema_version": HYBRID_VERSION,
        "pilot_id": plan["pilot_id"],
        "clips": clips,
        "science_shot_ids": sorted(science),
        "generated_selected_shot_ids": sorted(selected),
        "preview_fallback_shot_ids": preview_fallbacks,
        "pending_final_review_shot_ids": pending_review,
        "production_candidate": not preview_fallbacks and not pending_review,
        "publish_allowed": False,
    }


def assemble_hybrid_review(pilot_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    plan = _load(pilot_dir / "content-plan.json")
    natural = _load_optional_clip_manifest(artifact_dir / "clips" / "clip-manifest.json")
    science = _load(_latest_science_manifest(artifact_dir))
    selection_path = artifact_dir / "clips" / "generated" / "selection-manifest.json"
    selection = _load(selection_path) if selection_path.is_file() else None
    hybrid = build_hybrid_manifest(plan, natural, science, selection)
    manifest_path = artifact_dir / "clips" / "hybrid-v1" / "clip-manifest.json"
    atomic_write_json(manifest_path, hybrid)
    render = assemble_clip_plan(
        plan,
        hybrid,
        artifact_dir / "renders" / "hybrid-v1",
        narration_path=select_narration(artifact_dir),
        captions_path=pilot_dir / "captions.srt",
    )
    if not render.get("is_valid"):
        raise RuntimeError(f"Hybrid assembly failed: {render.get('errors')}")
    quality = automated_quality(render, hybrid, artifact_dir / "quality" / "hybrid-v1")
    return {
        "schema_version": HYBRID_VERSION,
        "pilot_id": plan["pilot_id"],
        "hybrid_manifest_path": str(manifest_path),
        "render": render,
        "quality": quality,
        "publish_allowed": False,
    }
