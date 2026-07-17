from __future__ import annotations

import json
from pathlib import Path

from src.p68_hybrid_review import (
    _latest_science_manifest,
    _load_optional_clip_manifest,
    _optional_narration,
    build_hybrid_manifest,
)


def clip(shot_id: str, provider: str, preview: bool) -> dict[str, object]:
    return {
        "shot_id": shot_id,
        "path": f"/{shot_id}.mp4",
        "provider": provider,
        "prompt_or_asset_reference": provider,
        "rights_status": "owned",
        "human_review_status": "pending_final_review",
        "preview_only": preview,
    }


def test_scientific_clip_replaces_preview_in_exact_plan_order() -> None:
    plan = {"pilot_id": "pilot", "shots": [{"shot_id": "S01"}, {"shot_id": "S02"}]}
    natural = {"clips": [clip("S01", "preview", True), clip("S02", "preview", True)]}
    science = {"clips": [clip("S02", "science", False)]}

    result = build_hybrid_manifest(plan, natural, science)

    assert [item["shot_id"] for item in result["clips"]] == ["S01", "S02"]
    assert result["clips"][1]["provider"] == "science"
    assert result["preview_fallback_shot_ids"] == ["S01"]
    assert result["production_candidate"] is False
    assert result["publish_allowed"] is False


def test_operator_selected_generation_replaces_natural_preview_but_not_science() -> None:
    plan = {"pilot_id": "pilot", "shots": [{"shot_id": "S01"}, {"shot_id": "S02"}]}
    natural = {"clips": [clip("S01", "preview", True), clip("S02", "preview", True)]}
    science = {"clips": [clip("S02", "science", False)]}
    generated = clip("S01", "rn-comfyui-wan", False)
    generated["human_review_status"] = "approved_for_assembly"
    selection = {"selected_clips": [generated]}

    result = build_hybrid_manifest(plan, natural, science, selection)

    assert [item["provider"] for item in result["clips"]] == ["rn-comfyui-wan", "science"]
    assert result["generated_selected_shot_ids"] == ["S01"]
    assert result["preview_fallback_shot_ids"] == []
    assert result["production_candidate"] is False


def test_science_only_pilot_does_not_require_natural_manifest() -> None:
    plan = {"pilot_id": "science-only", "shots": [{"shot_id": "S01"}, {"shot_id": "S02"}]}
    science = {"clips": [clip("S01", "science", False), clip("S02", "science", False)]}

    result = build_hybrid_manifest(plan, {"clips": []}, science)

    assert [item["provider"] for item in result["clips"]] == ["science", "science"]
    assert result["science_shot_ids"] == ["S01", "S02"]
    assert result["preview_fallback_shot_ids"] == []
    assert result["pending_final_review_shot_ids"] == ["S01", "S02"]
    assert result["production_candidate"] is False
    assert result["publish_allowed"] is False


def test_science_manifest_discovery_and_optional_inputs(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "gold" / "pilot"
    manifest = artifact_dir / "clips" / "scientific-v5" / "scientific-animation-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"clips": []}), encoding="utf-8")

    assert _latest_science_manifest(artifact_dir) == manifest
    assert _load_optional_clip_manifest(artifact_dir / "clips" / "clip-manifest.json") == {"clips": []}
    assert _optional_narration(artifact_dir) is None
