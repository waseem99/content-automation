from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p40_video_content_engine import (
    generate_video_package,
    normalize_video_brief,
    screen_rights_risks,
)

pytestmark = pytest.mark.integration

VALID_BRIEF = {
    "topic": "AI tools for small business owners",
    "platform": "youtube_shorts",
    "audience": "busy founders who want practical automation wins",
    "tone": "sharp, useful, cinematic",
    "duration_seconds": 45,
    "monetization_goal": "newsletter signups and future SaaS affiliate revenue",
    "content_format": "vertical_short",
    "must_use_points": ["show one workflow", "avoid hype", "make it practical"],
    "avoid": ["celebrity voice", "movie clip"],
    "source_notes": ["Use original screen recordings or owned mockups only."],
}


def test_brief_contract_validates_required_fields() -> None:
    invalid = normalize_video_brief({"topic": "AI"})
    assert invalid["is_valid"] is False
    assert "missing_audience" in invalid["validation_errors"]
    assert "missing_monetization_goal" in invalid["validation_errors"]

    valid = normalize_video_brief(VALID_BRIEF)
    assert valid["is_valid"] is True
    assert valid["platform"] == "youtube_shorts"
    assert valid["duration_seconds"] == 45


def test_package_contains_actual_video_content_sections() -> None:
    package = generate_video_package(VALID_BRIEF)
    assert package["schema_version"] == "p40.video_content_package.v1"
    assert package["is_valid"] is True
    for section in [
        "positioning",
        "concepts",
        "title_options",
        "hook",
        "retention_beats",
        "script",
        "scene_plan",
        "asset_requirements",
        "rights_risk",
        "scores",
        "production_brief",
    ]:
        assert section in package


def test_concepts_titles_hook_script_and_scenes_are_generated() -> None:
    package = generate_video_package(VALID_BRIEF)
    assert len(package["concepts"]) >= 3
    assert len(package["title_options"]) >= 5
    assert "most people miss" in package["hook"].lower()
    assert "framework" in package["script"].lower()
    assert "show one workflow" in package["script"]
    assert len(package["retention_beats"]) >= 5
    assert len(package["scene_plan"]) == len(package["retention_beats"])
    assert all("visual_direction" in scene for scene in package["scene_plan"])


def test_rights_risk_flags_unsafe_references_and_suggests_safer_options() -> None:
    risks = screen_rights_risks("Make it exactly like Marvel with a famous song and movie clip")
    assert risks["risk_level"] == "high"
    categories = {item["category"] for item in risks["findings"]}
    assert "copyrighted_character_or_franchise" in categories
    assert "commercial_music_or_clip" in categories
    assert "copied_style_or_premise" in categories
    assert risks["legal_clearance_claimed"] is False


def test_scores_are_numeric_and_do_not_guarantee_monetization() -> None:
    package = generate_video_package(VALID_BRIEF)
    scores = package["scores"]
    assert 0 <= scores["engagement_score"] <= 100
    assert 0 <= scores["monetization_readiness_score"] <= 100
    assert scores["monetization_guaranteed"] is False
    assert scores["subscores"]["rights_safety"] >= 70


def test_asset_requirements_are_production_safe() -> None:
    package = generate_video_package(VALID_BRIEF)
    asset_text = json.dumps(package["asset_requirements"]).lower()
    assert "licensed" in asset_text
    assert "no celebrity imitation" in asset_text
    assert package["production_brief"]["review_required_before_publish"] is True


def test_example_file_tracks_real_sections() -> None:
    example = json.loads(Path("docs/operations/p40-video-package-example.json").read_text(encoding="utf-8"))
    package = generate_video_package(example["example_brief"])
    for section in example["expected_output_sections"]:
        assert section in package
    assert example["guardrails"]["no_upload_or_publish"] is True
    assert example["guardrails"]["monetization_guaranteed"] is False
