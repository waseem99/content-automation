from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p40_video_content_engine import generate_video_package
from src.p41_rights_safety_engine import (
    analyze_rights_safety,
    build_asset_manifest,
    detect_rights_risks,
    generate_safer_rewrites,
    normalize_rights_payload,
    score_rights_safety,
)

pytestmark = pytest.mark.integration

SAFE_BRIEF = {
    "topic": "AI tools for small business owners",
    "platform": "youtube_shorts",
    "audience": "busy founders",
    "duration_seconds": 45,
    "monetization_goal": "newsletter signups",
    "must_use_points": ["show one workflow"],
    "source_notes": ["Use owned mockups and licensed music."],
}

RISKY_PAYLOAD = {
    "platform": "youtube_shorts",
    "title_options": ["Make AI Automation Like Marvel"],
    "hook": "Use a MrBeast voice and a famous song.",
    "script": "Cut in a Netflix clip and make it exactly like Star Wars with TikTok audio.",
    "scene_plan": [{"visual_direction": "Screen record someone else's video."}],
    "asset_requirements": [{"asset": "music", "requirement": "famous song"}],
}


def test_rights_input_contract_accepts_p40_package() -> None:
    package = generate_video_package(SAFE_BRIEF)
    normalized = normalize_rights_payload(package)
    assert normalized["is_valid"] is True
    assert normalized["fields"]["platform"] == "youtube_shorts"
    assert "ai tools" in normalized["analysis_text"]


def test_input_contract_rejects_empty_payload() -> None:
    normalized = normalize_rights_payload({})
    assert normalized["is_valid"] is False
    assert "missing_analyzable_content" in normalized["validation_errors"]


def test_risk_detection_finds_core_categories() -> None:
    findings = detect_rights_risks(RISKY_PAYLOAD)
    categories = {item["category"] for item in findings}
    assert "copyrighted_franchise_or_character" in categories
    assert "celebrity_likeness_or_voice" in categories
    assert "commercial_music_or_audio" in categories
    assert "third_party_clip_or_footage" in categories
    assert "copied_premise_or_style" in categories
    assert "brand_or_trademark_dependency" in categories
    assert all("why_it_matters" in item for item in findings)


def test_safer_rewrites_are_generated_for_findings() -> None:
    findings = detect_rights_risks(RISKY_PAYLOAD)
    rewrites = generate_safer_rewrites(findings)
    assert len(rewrites) == len(findings)
    assert any("original" in item["example_rewrite"].lower() for item in rewrites)
    assert all("rewrite_strategy" in item for item in rewrites)


def test_asset_manifest_tracks_clearance_evidence() -> None:
    manifest = build_asset_manifest(RISKY_PAYLOAD)
    categories = {item["asset_category"] for item in manifest}
    assert {"voiceover", "music", "footage", "graphics", "fonts"}.issubset(categories)
    required_assets = [item for item in manifest if item["required"]]
    assert required_assets
    assert all(item["clearance_status"] in {"needs_evidence", "not_required_yet"} for item in manifest)


def test_scores_and_publish_gate_block_high_risk_payload() -> None:
    report = analyze_rights_safety(RISKY_PAYLOAD)
    assert report["schema_version"] == "p41.rights_safety_report.v1"
    assert report["is_valid"] is True
    assert report["scores"]["legal_clearance_claimed"] is False
    assert report["scores"]["monetization_guaranteed"] is False
    assert report["publish_gate"]["gate"] == "block"
    assert report["publish_gate"]["blocker_reasons"]
    assert any("reused-content" in flag for flag in report["platform_monetization_safety_flags"])


def test_safe_package_gets_report_sections_and_no_legal_claims() -> None:
    package = generate_video_package(SAFE_BRIEF)
    report = analyze_rights_safety(package)
    for section in [
        "rights_risk_inventory",
        "safer_rewrite_suggestions",
        "asset_source_manifest",
        "originality_and_transformation_notes",
        "platform_monetization_safety_flags",
        "scores",
        "publish_gate",
    ]:
        assert section in report
    assert report["scores"]["legal_clearance_claimed"] is False
    assert report["scores"]["monetization_guaranteed"] is False
    assert report["publish_gate"]["gate"] in {"pass", "revise"}


def test_score_function_is_json_serializable() -> None:
    findings = detect_rights_risks(RISKY_PAYLOAD)
    manifest = build_asset_manifest(RISKY_PAYLOAD)
    score = score_rights_safety(findings, manifest)
    encoded = json.dumps(score, sort_keys=True)
    assert "overall_safety_score" in encoded


def test_example_file_matches_engine_output() -> None:
    example = json.loads(Path("docs/operations/p41-rights-safety-example.json").read_text(encoding="utf-8"))
    report = analyze_rights_safety(example["example_payload"])
    for section in example["expected_output_sections"]:
        assert section in report
    assert example["guardrails"]["legal_clearance_claimed"] is False
    assert example["guardrails"]["no_upload_or_publish"] is True
