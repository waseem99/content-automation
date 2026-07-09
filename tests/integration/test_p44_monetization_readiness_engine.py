from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p40_video_content_engine import generate_video_package
from src.p41_rights_safety_engine import analyze_rights_safety
from src.p42_engagement_retention_engine import build_engagement_scorecard
from src.p43_production_pack_engine import build_production_handoff_pack
from src.p44_monetization_readiness_engine import (
    build_monetization_readiness_report,
    generate_activation_notes,
    generate_metadata_pack,
    generate_repurposing_plan,
    normalize_monetization_payload,
    readiness_recommendation,
    score_monetization_routes,
)

pytestmark = pytest.mark.integration

BRIEF = {
    "topic": "AI automation",
    "platform": "youtube_shorts",
    "audience": "busy founders",
    "duration_seconds": 45,
    "monetization_goal": "newsletter signups and SaaS affiliate revenue",
    "must_use_points": ["show one workflow"],
}


def _bundle() -> dict:
    video = generate_video_package(BRIEF)
    rights = analyze_rights_safety(video)
    engagement = build_engagement_scorecard(video)
    production = build_production_handoff_pack({
        "video_package": video,
        "rights_report": rights,
        "engagement_scorecard": engagement,
    })
    return {
        "video_package": video,
        "rights_report": rights,
        "engagement_scorecard": engagement,
        "production_pack": production,
    }


def test_input_contract_accepts_full_bundle() -> None:
    normalized = normalize_monetization_payload(_bundle())
    assert normalized["is_valid"] is True
    assert normalized["fields"]["platform"] == "youtube_shorts"
    assert normalized["fields"]["production_ready"] is True
    assert normalized["fields"]["engagement_score"] >= 0


def test_input_contract_rejects_missing_video_package() -> None:
    normalized = normalize_monetization_payload({})
    assert normalized["is_valid"] is False
    assert "missing_video_package" in normalized["validation_errors"]


def test_route_scores_cover_core_monetization_paths() -> None:
    fields = normalize_monetization_payload(_bundle())["fields"]
    scores = score_monetization_routes(fields)
    for route in ["ad_revenue", "sponsorship", "affiliate", "lead_gen", "product_service", "ip_library"]:
        assert route in scores["route_scores"]
        assert 0 <= scores["route_scores"][route] <= 100
    assert len(scores["best_routes"]) == 3
    assert scores["monetization_guaranteed"] is False


def test_metadata_pack_is_channel_ready() -> None:
    fields = normalize_monetization_payload(_bundle())["fields"]
    metadata = generate_metadata_pack(fields)
    assert metadata["title"]
    assert metadata["description"]
    assert metadata["tags"]
    assert metadata["hashtags"]
    assert metadata["pinned_comment"]
    assert metadata["primary_cta"]


def test_activation_notes_are_practical_and_non_guaranteed() -> None:
    fields = normalize_monetization_payload(_bundle())["fields"]
    notes = generate_activation_notes(fields)
    assert notes["sponsor_categories"]
    assert notes["affiliate_categories"]
    assert notes["lead_magnet_ideas"]
    assert notes["conversion_guaranteed"] is False
    assert notes["sponsorship_guaranteed"] is False


def test_repurposing_plan_covers_channels() -> None:
    fields = normalize_monetization_payload(_bundle())["fields"]
    plan = generate_repurposing_plan(fields)
    formats = {item["format"] for item in plan}
    assert {"youtube_shorts", "instagram_reels", "tiktok", "longform", "carousel_newsletter"}.issubset(formats)


def test_final_report_contains_required_sections_and_guardrails() -> None:
    report = build_monetization_readiness_report(_bundle())
    assert report["schema_version"] == "p44.monetization_readiness_report.v1"
    assert report["is_valid"] is True
    for section in [
        "monetization_route_fit",
        "metadata_pack",
        "activation_notes",
        "repurposing_plan",
        "compliance_caveats",
        "final_recommendation",
    ]:
        assert section in report
    assert report["monetization_guaranteed"] is False
    assert report["revenue_guaranteed"] is False
    assert report["upload_or_publish_performed"] is False
    assert report["platform_api_called"] is False
    assert report["legal_or_tax_advice_given"] is False


def test_blocked_rights_gate_not_ready() -> None:
    fields = normalize_monetization_payload(_bundle())["fields"]
    fields["rights_gate"] = {"gate": "block"}
    scores = score_monetization_routes(fields)
    recommendation = readiness_recommendation(scores, fields)
    assert recommendation["status"] == "not_ready"
    assert "Resolve rights blockers before production or publishing." in recommendation["next_actions"]


def test_example_file_matches_engine_output() -> None:
    example = json.loads(Path("docs/operations/p44-monetization-example.json").read_text(encoding="utf-8"))
    report = build_monetization_readiness_report(example["example_payload"])
    for section in example["expected_output_sections"]:
        assert section in report
    for key, expected in example["guardrails"].items():
        assert report[key] is expected
