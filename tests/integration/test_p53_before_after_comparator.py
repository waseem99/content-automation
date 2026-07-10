from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p53_before_after_comparator import (
    build_before_after_comparison,
    compare_dimensions,
    revised_index_to_qa_source,
    select_production_candidates,
    write_before_after_files,
)

pytestmark = pytest.mark.integration

ORIGINAL_QA = {
    "schema_version": "p50.creative_qa_pack.v1",
    "is_valid": True,
    "scorecards": [
        {
            "pilot_number": 1,
            "pilot_name": "ai-automation-founder-short",
            "topic": "AI automation for small business owners",
            "platform": "youtube_shorts",
            "output_dir": "outputs/pilots/ai-automation-founder-short",
            "baseline_scores": {
                "hook_strength": 70,
                "clarity": 75,
                "retention_potential": 72,
                "platform_fit": 80,
                "originality": 75,
                "rights_readiness": 88,
                "monetization_fit": 76,
                "production_feasibility": 84,
            },
            "weighted_overall_score": 77,
            "recommendation": "revise_before_production",
        },
        {
            "pilot_number": 2,
            "pilot_name": "weak-rights-pilot",
            "topic": "risky trend remix",
            "platform": "tiktok",
            "output_dir": "outputs/pilots/weak-rights-pilot",
            "baseline_scores": {
                "hook_strength": 80,
                "clarity": 80,
                "retention_potential": 80,
                "platform_fit": 80,
                "originality": 55,
                "rights_readiness": 45,
                "monetization_fit": 65,
                "production_feasibility": 70,
            },
            "weighted_overall_score": 68,
            "recommendation": "block",
        },
    ],
}

REVISED_INDEX = {
    "schema_version": "p52.revised_pilot_index.v1",
    "revised_pilots": [
        {
            "source_pilot_name": "ai-automation-founder-short",
            "revised_pilot_name": "ai-automation-founder-short-revised",
            "topic": "AI automation for small business owners",
            "platform": "youtube_shorts",
            "revised_output_dir": "outputs/revised/ai-automation-founder-short-revised",
            "is_valid": True,
            "pipeline_status": "ready_for_human_review",
            "rights_gate": "pass",
            "engagement_score": 91,
            "monetization_status": "ready_for_human_review",
            "production_ready": True,
            "template_platforms": ["youtube_shorts", "instagram_reels", "tiktok", "youtube_long", "carousel_newsletter"],
        },
        {
            "source_pilot_name": "weak-rights-pilot",
            "revised_pilot_name": "weak-rights-pilot-revised",
            "topic": "risky trend remix",
            "platform": "tiktok",
            "revised_output_dir": "outputs/revised/weak-rights-pilot-revised",
            "is_valid": True,
            "pipeline_status": "revise",
            "rights_gate": "block",
            "engagement_score": 60,
            "monetization_status": "not_ready",
            "production_ready": False,
            "template_platforms": ["tiktok"],
        },
    ],
}


def test_revised_index_to_qa_source() -> None:
    source = revised_index_to_qa_source(REVISED_INDEX["revised_pilots"])
    assert "pilots" in source
    assert source["pilots"][0]["pilot_name"] == "ai-automation-founder-short-revised"
    assert source["pilots"][0]["rights_gate"] == "pass"


def test_build_before_after_comparison() -> None:
    result = build_before_after_comparison(ORIGINAL_QA, REVISED_INDEX)
    assert result["schema_version"] == "p53.before_after_comparison.v1"
    assert result["is_valid"] is True
    assert result["comparison_summary"]["pilot_count"] == 2
    assert result["comparisons"][0]["source_pilot_name"] == "ai-automation-founder-short"
    assert result["comparisons"][0]["score_delta"] > 0


def test_compare_dimensions() -> None:
    deltas = compare_dimensions({"hook_strength": 70, "clarity": 80}, {"hook_strength": 90, "clarity": 75})
    assert deltas["hook_strength"] == 20
    assert deltas["clarity"] == -5


def test_candidate_shortlist_groups() -> None:
    result = build_before_after_comparison(ORIGINAL_QA, REVISED_INDEX)
    shortlist = select_production_candidates(result["comparisons"])
    assert "produce_after_human_approval" in shortlist
    assert "revise_again" in shortlist
    assert "drop_or_rework" in shortlist
    assert shortlist["drop_or_rework"]


def test_write_before_after_files(tmp_path: Path) -> None:
    result = write_before_after_files(ORIGINAL_QA, REVISED_INDEX, tmp_path)
    assert result["is_valid"] is True
    assert Path(result["before_after_comparison_path"]).exists()
    assert Path(result["production_candidate_shortlist_path"]).exists()
    assert Path(result["revised_qa_scorecards_path"]).exists()
    assert Path(result["before_after_report_path"]).exists()


def test_file_input_paths(tmp_path: Path) -> None:
    original_path = tmp_path / "qa_scorecards.json"
    revised_path = tmp_path / "revised_pilot_index.json"
    original_path.write_text(json.dumps(ORIGINAL_QA), encoding="utf-8")
    revised_path.write_text(json.dumps(REVISED_INDEX), encoding="utf-8")
    result = write_before_after_files(original_path, revised_path, tmp_path)
    assert result["is_valid"] is True
    assert result["comparison_summary"]["human_approval_required_before_production"] is True


def test_invalid_inputs_fail_cleanly() -> None:
    result = build_before_after_comparison({"scorecards": []}, {})
    assert result["is_valid"] is False
    assert "missing_revised_pilots" in result["validation_errors"]


def test_guardrails_are_local_only() -> None:
    result = build_before_after_comparison(ORIGINAL_QA, REVISED_INDEX)
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["api_server_started"] is False
    assert result["external_calls_performed"] is False
    assert result["rendering_performed"] is False
    assert result["asset_download_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["improvement_guaranteed"] is False
    assert result["performance_guaranteed"] is False
    assert result["human_approval_required_before_production"] is True
