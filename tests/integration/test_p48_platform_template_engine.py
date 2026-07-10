from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p45_video_pipeline_orchestrator import run_video_content_pipeline
from src.p46_local_export_pack import build_local_export_pack
from src.p48_platform_template_engine import (
    TARGET_PLATFORMS,
    adapt_cta,
    adapt_hook,
    build_platform_template_pack,
    normalize_template_payload,
    render_platform_templates_json,
)

pytestmark = pytest.mark.integration

VALID_BRIEF = {
    "topic": "AI automation for small business owners",
    "platform": "youtube_shorts",
    "audience": "busy founders who want practical automation wins",
    "tone": "sharp, useful, cinematic",
    "duration_seconds": 45,
    "monetization_goal": "newsletter signups and SaaS affiliate revenue",
    "content_format": "vertical_short",
    "must_use_points": ["show one workflow", "avoid hype", "make it practical"],
    "avoid": ["celebrity voice", "movie clip"],
    "source_notes": ["Use owned mockups and licensed music only."],
}


def test_normalize_accepts_raw_brief() -> None:
    normalized = normalize_template_payload(VALID_BRIEF)
    assert normalized["is_valid"] is True
    assert normalized["fields"]["topic"] == VALID_BRIEF["topic"]
    assert normalized["fields"]["primary_platform"] == "youtube_shorts"


def test_normalize_accepts_p45_and_p46_payloads() -> None:
    pipeline = run_video_content_pipeline(VALID_BRIEF)
    assert normalize_template_payload(pipeline)["is_valid"] is True
    export_pack = build_local_export_pack(pipeline)
    assert normalize_template_payload(export_pack)["is_valid"] is True


def test_template_pack_contains_all_platforms() -> None:
    pack = build_platform_template_pack(VALID_BRIEF)
    assert pack["schema_version"] == "p48.platform_template_pack.v1"
    assert pack["is_valid"] is True
    assert set(pack["templates"]) == set(TARGET_PLATFORMS)
    assert pack["recommended_primary_platform"] == "youtube_shorts"


def test_each_platform_has_required_creative_fields() -> None:
    pack = build_platform_template_pack(VALID_BRIEF)
    for platform, template in pack["templates"].items():
        assert template["platform"] == platform
        for field in [
            "title",
            "adapted_hook",
            "adapted_cta",
            "hook_style",
            "pacing_rules",
            "caption_style",
            "scene_count_guidance",
            "metadata_guidance",
            "storyboard_adaptation_notes",
            "export_notes",
            "risk_compliance_notes",
        ]:
            assert template[field]
        assert template["performance_guaranteed"] is False


def test_platform_adaptations_are_not_generic() -> None:
    pack = build_platform_template_pack(VALID_BRIEF)
    hooks = {platform: template["adapted_hook"] for platform, template in pack["templates"].items()}
    ctas = {platform: template["adapted_cta"] for platform, template in pack["templates"].items()}
    assert hooks["tiktok"] != hooks["youtube_long"]
    assert ctas["instagram_reels"] != ctas["youtube_long"]
    assert "template" in ctas["tiktok"].lower()
    assert "download" in ctas["youtube_long"].lower()


def test_target_platform_filtering() -> None:
    pack = build_platform_template_pack(VALID_BRIEF, target_platforms=["tiktok", "youtube_long"])
    assert set(pack["templates"]) == {"tiktok", "youtube_long"}


def test_helper_adaptations_are_platform_specific() -> None:
    fields = normalize_template_payload(VALID_BRIEF)["fields"]
    assert "hard way" in adapt_hook("tiktok", fields).lower()
    assert "full" in adapt_hook("youtube_long", fields).lower()
    assert "share" in adapt_cta("instagram_reels", fields).lower()


def test_json_renderer_is_serializable() -> None:
    rendered = render_platform_templates_json(VALID_BRIEF)
    decoded = json.loads(rendered)
    assert decoded["schema_version"] == "p48.platform_template_pack.v1"
    assert decoded["platform_api_called"] is False


def test_example_file_matches_engine_output() -> None:
    example = json.loads(Path("docs/operations/p48-platform-template-example.json").read_text(encoding="utf-8"))
    pack = build_platform_template_pack(example["example_brief"])
    assert set(pack["templates"]) == set(example["expected_platforms"])
    for platform in example["expected_platforms"]:
        for field in example["expected_template_fields"]:
            assert field in pack["templates"][platform]
    for key, expected in example["guardrails"].items():
        assert pack[key] is expected
