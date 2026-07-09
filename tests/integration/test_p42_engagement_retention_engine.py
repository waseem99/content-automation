from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p40_video_content_engine import generate_video_package
from src.p42_engagement_retention_engine import (
    build_engagement_scorecard,
    estimate_retention_curve,
    generate_cta_variants,
    generate_hook_variants,
    normalize_engagement_payload,
    score_engagement_dimensions,
    score_hook,
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

WEAK_PAYLOAD = {
    "platform": "youtube_shorts",
    "duration_seconds": 45,
    "audience": "small business owners",
    "topic": "marketing",
    "hook": "Marketing is important.",
    "script": "Marketing helps businesses grow.",
    "retention_beats": [],
    "scene_plan": [],
}


def test_input_contract_accepts_p40_package() -> None:
    package = generate_video_package(BRIEF)
    normalized = normalize_engagement_payload(package)
    assert normalized["is_valid"] is True
    assert normalized["fields"]["platform"] == "youtube_shorts"
    assert normalized["fields"]["hook"]
    assert normalized["fields"]["script"]


def test_input_contract_rejects_missing_hook_or_script() -> None:
    normalized = normalize_engagement_payload({"hook": "Only hook"})
    assert normalized["is_valid"] is False
    assert "missing_script" in normalized["validation_errors"]


def test_hook_score_outputs_diagnostics_and_fixes() -> None:
    normalized = normalize_engagement_payload(WEAK_PAYLOAD)
    result = score_hook(normalized["fields"])
    assert 0 <= result["hook_score"] <= 100
    assert "curiosity_gap" in result["diagnostics"]
    assert result["fixes"]


def test_retention_curve_estimates_pacing_and_issues() -> None:
    normalized = normalize_engagement_payload(WEAK_PAYLOAD)
    result = estimate_retention_curve(normalized["fields"])
    assert 0 <= result["pacing_score"] <= 100
    assert result["estimated_curve"]
    assert any("retention beats" in item for item in result["issues"])


def test_engagement_dimensions_score_core_signals() -> None:
    package = generate_video_package(BRIEF)
    fields = normalize_engagement_payload(package)["fields"]
    result = score_engagement_dimensions(fields)
    for key in ["emotional_pull", "novelty", "clarity", "shareability", "saveability", "rewatch_loop", "cta_quality"]:
        assert key in result["dimension_scores"]
        assert 0 <= result["dimension_scores"][key] <= 100
        assert key in result["notes"]


def test_variants_are_generated() -> None:
    fields = normalize_engagement_payload(generate_video_package(BRIEF))["fields"]
    assert len(generate_hook_variants(fields)) >= 5
    assert len(generate_cta_variants(fields)) >= 3


def test_scorecard_contains_required_sections_and_no_guarantees() -> None:
    package = generate_video_package(BRIEF)
    result = build_engagement_scorecard(package)
    assert result["schema_version"] == "p42.engagement_scorecard.v1"
    assert result["is_valid"] is True
    for section in [
        "hook_diagnostics",
        "retention_analysis",
        "engagement_dimensions",
        "alternate_hooks",
        "cta_variants",
        "improvement_plan",
        "overall_engagement_score",
    ]:
        assert section in result
    assert result["performance_guaranteed"] is False
    assert result["live_analytics_used"] is False


def test_example_file_matches_engine_output() -> None:
    example = json.loads(Path("docs/operations/p42-engagement-example.json").read_text(encoding="utf-8"))
    result = build_engagement_scorecard(example["example_payload"])
    for section in example["expected_output_sections"]:
        assert section in result
    assert example["guardrails"]["live_analytics_used"] is False
    assert example["guardrails"]["no_upload_or_publish"] is True
