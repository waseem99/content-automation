from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p40_video_content_engine import generate_video_package
from src.p41_rights_safety_engine import analyze_rights_safety
from src.p42_engagement_retention_engine import build_engagement_scorecard
from src.p43_production_pack_engine import (
    build_production_handoff_pack,
    generate_asset_checklist,
    generate_shot_list,
    generate_storyboard_frames,
    generate_thumbnail_directions,
    generate_voiceover_caption_map,
    normalize_production_payload,
)

pytestmark = pytest.mark.integration

BRIEF = {
    "topic": "AI automation",
    "platform": "youtube_shorts",
    "audience": "busy founders",
    "duration_seconds": 45,
    "monetization_goal": "newsletter signups",
    "must_use_points": ["show one workflow"],
}


def _bundle() -> dict:
    video = generate_video_package(BRIEF)
    return {
        "video_package": video,
        "rights_report": analyze_rights_safety(video),
        "engagement_scorecard": build_engagement_scorecard(video),
    }


def test_input_contract_accepts_p40_p41_p42_bundle() -> None:
    normalized = normalize_production_payload(_bundle())
    assert normalized["is_valid"] is True
    assert normalized["fields"]["platform"] == "youtube_shorts"
    assert normalized["fields"]["script"]
    assert normalized["fields"]["scene_plan"]


def test_input_contract_rejects_missing_script_or_scene_plan() -> None:
    normalized = normalize_production_payload({"script": ""})
    assert normalized["is_valid"] is False
    assert "missing_script" in normalized["validation_errors"]
    assert "missing_scene_plan" in normalized["validation_errors"]


def test_storyboard_frames_are_generated() -> None:
    fields = normalize_production_payload(_bundle())["fields"]
    frames = generate_storyboard_frames(fields)
    assert frames
    assert frames[0]["frame_number"] == 1
    assert "visual_direction" in frames[0]
    assert "production_risk_note" in frames[0]


def test_shot_list_maps_to_frames() -> None:
    fields = normalize_production_payload(_bundle())["fields"]
    frames = generate_storyboard_frames(fields)
    shots = generate_shot_list(frames, fields)
    assert len(shots) == len(frames)
    assert shots[0]["shot_id"] == "S01"
    assert "caption_style" in shots[0]
    assert "editor_note" in shots[0]


def test_voiceover_caption_map_splits_script() -> None:
    fields = normalize_production_payload(_bundle())["fields"]
    frames = generate_storyboard_frames(fields)
    timing = generate_voiceover_caption_map(frames, fields)
    assert len(timing) == len(frames)
    assert timing[0]["voiceover_segment"]
    assert len(timing[0]["caption_text"].split()) <= 9


def test_thumbnail_and_asset_checklist_are_production_ready() -> None:
    fields = normalize_production_payload(_bundle())["fields"]
    thumb = generate_thumbnail_directions(fields)
    assets = generate_asset_checklist(fields)
    assert thumb["cover_text"]
    assert "safe_asset_notes" in thumb
    categories = {asset["asset_category"] for asset in assets}
    assert {"voiceover", "music", "footage", "graphics", "captions", "font", "thumbnail", "source_evidence"}.issubset(categories)


def test_final_pack_contains_required_sections_and_guardrails() -> None:
    pack = build_production_handoff_pack(_bundle())
    assert pack["schema_version"] == "p43.production_handoff_pack.v1"
    assert pack["is_valid"] is True
    for section in [
        "production_brief",
        "storyboard_frames",
        "shot_list",
        "voiceover_caption_timing",
        "asset_checklist",
        "thumbnail_directions",
        "editor_instructions",
    ]:
        assert section in pack
    assert pack["rendering_performed"] is False
    assert pack["external_calls_performed"] is False
    assert pack["upload_or_publish_performed"] is False
    assert pack["performance_guaranteed"] is False


def test_example_file_matches_engine_output() -> None:
    example = json.loads(Path("docs/operations/p43-production-pack-example.json").read_text(encoding="utf-8"))
    pack = build_production_handoff_pack(example["example_payload"])
    for section in example["expected_output_sections"]:
        assert section in pack
    assert example["guardrails"]["rendering_performed"] is False
    assert example["guardrails"]["upload_or_publish_performed"] is False
