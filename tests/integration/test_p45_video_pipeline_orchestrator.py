from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p45_video_pipeline_orchestrator import (
    aggregate_pipeline_status,
    run_video_content_pipeline,
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


def test_pipeline_runs_end_to_end() -> None:
    result = run_video_content_pipeline(VALID_BRIEF)
    assert result["schema_version"] == "p45.end_to_end_video_pipeline.v1"
    assert result["is_valid"] is True
    for section in [
        "video_package",
        "rights_report",
        "engagement_scorecard",
        "production_pack",
        "monetization_report",
        "summary",
    ]:
        assert section in result
    assert result["summary"]["core_outputs_present"] is True


def test_pipeline_invalid_brief_fails_cleanly() -> None:
    result = run_video_content_pipeline({"topic": "AI"})
    assert result["is_valid"] is False
    assert result["pipeline_status"] == "invalid_brief"
    assert "missing_audience" in result["validation_errors"]
    assert "missing_monetization_goal" in result["validation_errors"]


def test_pipeline_status_and_guardrails() -> None:
    result = run_video_content_pipeline(VALID_BRIEF)
    assert result["pipeline_status"] in {"ready_for_human_review", "revise", "block"}
    assert result["external_calls_performed"] is False
    assert result["rendering_performed"] is False
    assert result["asset_download_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["live_analytics_used"] is False
    assert result["monetization_guaranteed"] is False
    assert result["revenue_guaranteed"] is False
    assert result["human_review_required_before_publish"] is True


def test_summary_has_scores_gates_blockers_and_next_actions() -> None:
    result = run_video_content_pipeline(VALID_BRIEF)
    summary = result["summary"]
    assert "rights_gate" in summary
    assert "engagement_score" in summary
    assert "monetization_status" in summary
    assert "production_ready" in summary
    assert isinstance(summary["blockers"], list)
    assert isinstance(summary["next_actions"], list)
    assert summary["next_actions"]


def test_block_status_when_rights_gate_blocks() -> None:
    result = run_video_content_pipeline(VALID_BRIEF)
    rights_report = dict(result["rights_report"])
    rights_report["publish_gate"] = {"gate": "block", "blocker_reasons": ["Unsafe clip"]}
    summary = aggregate_pipeline_status(
        result["video_package"],
        rights_report,
        result["engagement_scorecard"],
        result["production_pack"],
        result["monetization_report"],
    )
    assert summary["pipeline_status"] == "block"
    assert "Unsafe clip" in summary["blockers"]


def test_pipeline_output_is_json_serializable() -> None:
    result = run_video_content_pipeline(VALID_BRIEF)
    encoded = json.dumps(result, sort_keys=True)
    assert "p45.end_to_end_video_pipeline.v1" in encoded


def test_example_file_matches_pipeline() -> None:
    example = json.loads(Path("docs/operations/p45-video-pipeline-example.json").read_text(encoding="utf-8"))
    result = run_video_content_pipeline(example["example_brief"])
    for section in example["expected_output_sections"]:
        assert section in result
    for key, expected in example["guardrails"].items():
        assert result[key] is expected
