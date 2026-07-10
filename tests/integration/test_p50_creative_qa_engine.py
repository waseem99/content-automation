from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p49_pilot_batch_runner import DEFAULT_PILOT_BRIEFS, run_pilot_batch
from src.p50_creative_qa_engine import (
    build_batch_qa_summary,
    build_creative_qa_pack,
    load_pilot_index,
    normalize_qa_input,
    render_batch_summary_markdown,
    render_scorecard_markdown,
    score_pilot,
    write_creative_qa_files,
)

pytestmark = pytest.mark.integration


def _batch(tmp_path: Path) -> dict:
    return run_pilot_batch(DEFAULT_PILOT_BRIEFS[:2], tmp_path, overwrite=True)


def test_normalize_accepts_p49_batch_result(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    normalized = normalize_qa_input(batch)
    assert normalized["is_valid"] is True
    assert len(normalized["pilots"]) == 2
    assert normalized["pilots"][0]["pilot_name"]


def test_load_pilot_index_from_file(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    index = load_pilot_index(batch["pilot_index_path"])
    assert "pilots" in index
    assert len(index["pilots"]) == 2


def test_invalid_input_returns_validation_error() -> None:
    result = build_creative_qa_pack({"pilots": []})
    assert result["is_valid"] is False
    assert "missing_pilots" in result["validation_errors"]


def test_score_pilot_has_all_dimensions(tmp_path: Path) -> None:
    pilot = normalize_qa_input(_batch(tmp_path))["pilots"][0]
    scorecard = score_pilot(pilot)
    expected = {
        "hook_strength",
        "clarity",
        "retention_potential",
        "platform_fit",
        "originality",
        "rights_readiness",
        "monetization_fit",
        "production_feasibility",
    }
    assert expected == set(scorecard["baseline_scores"])
    assert 0 <= scorecard["weighted_overall_score"] <= 100
    assert scorecard["recommendation"] in {"accept_for_human_review", "revise_before_production", "block"}
    assert scorecard["human_review_required_before_production"] is True


def test_creative_qa_pack_contains_summary_and_rubric(tmp_path: Path) -> None:
    result = build_creative_qa_pack(_batch(tmp_path))
    assert result["schema_version"] == "p50.creative_qa_pack.v1"
    assert result["is_valid"] is True
    assert result["pilot_count"] == 2
    assert result["scorecards"]
    assert result["batch_summary"]["batch_decision"] in {
        "accept_for_manual_production_review",
        "revise_pilots_before_production",
        "block",
    }
    assert result["human_review_required"] is True
    assert result["human_review_fields"]["approval_status"] == "pending"


def test_batch_summary_aggregates_recommendations(tmp_path: Path) -> None:
    scorecards = build_creative_qa_pack(_batch(tmp_path))["scorecards"]
    summary = build_batch_qa_summary(scorecards)
    assert summary["pilot_count"] == 2
    assert summary["average_score"] >= 0
    assert summary["human_review_required"] is True


def test_markdown_renderers_include_human_review(tmp_path: Path) -> None:
    qa_pack = build_creative_qa_pack(_batch(tmp_path))
    card_md = render_scorecard_markdown(qa_pack["scorecards"][0])
    summary_md = render_batch_summary_markdown(qa_pack)
    assert "Human Review" in card_md
    assert "Batch Creative QA Summary" in summary_md
    assert "Human review is required" in summary_md


def test_write_creative_qa_files(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    result = write_creative_qa_files(batch)
    root = Path(result["output_root"])
    assert result["is_valid"] is True
    assert (root / "qa_scorecards.json").exists()
    assert (root / "qa_summary.md").exists()
    assert Path(result["qa_scorecard_dir"]).exists()
    assert len(list(Path(result["qa_scorecard_dir"]).glob("*.md"))) == 2


def test_write_creative_qa_files_from_index_path(tmp_path: Path) -> None:
    batch = _batch(tmp_path)
    result = write_creative_qa_files(batch["pilot_index_path"])
    assert result["is_valid"] is True
    assert Path(result["qa_summary_path"]).exists()


def test_guardrails_are_local_only(tmp_path: Path) -> None:
    result = build_creative_qa_pack(_batch(tmp_path))
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["api_server_started"] is False
    assert result["external_calls_performed"] is False
    assert result["rendering_performed"] is False
    assert result["asset_download_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["performance_guaranteed"] is False


def test_example_file_matches_contract() -> None:
    example = json.loads(Path("docs/operations/p50-creative-qa-example.json").read_text(encoding="utf-8"))
    result = build_creative_qa_pack(example["example_pilot_index"])
    assert result["is_valid"] is True
    for key, expected in example["guardrails"].items():
        assert result[key] is expected
