from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p49_pilot_batch_runner import DEFAULT_PILOT_BRIEFS, run_pilot_batch
from src.p50_creative_qa_engine import build_creative_qa_pack, write_creative_qa_files
from src.p51_revision_planner import (
    build_pilot_revision_pack,
    build_revision_plan,
    load_qa_scorecards,
    normalize_revision_input,
    revision_tasks_for_scorecard,
    write_revision_files,
)

pytestmark = pytest.mark.integration


def _qa_pack(tmp_path: Path) -> dict:
    batch = run_pilot_batch(DEFAULT_PILOT_BRIEFS[:2], tmp_path / "pilots", overwrite=True)
    return build_creative_qa_pack(batch)


def test_revision_input_accepts_qa_pack() -> None:
    qa_pack = {
        "scorecards": [
            {
                "pilot_name": "test-pilot",
                "topic": "test topic",
                "platform": "youtube_shorts",
                "baseline_scores": {"hook_strength": 70},
                "weighted_overall_score": 72,
                "recommendation": "revise_before_production",
            }
        ]
    }
    normalized = normalize_revision_input(qa_pack)
    assert normalized["is_valid"] is True
    assert normalized["scorecards"][0]["pilot_name"] == "test-pilot"


def test_revision_input_accepts_qa_scorecards_path(tmp_path: Path) -> None:
    qa_pack = _qa_pack(tmp_path)
    path = tmp_path / "qa_scorecards.json"
    path.write_text(json.dumps(qa_pack), encoding="utf-8")
    loaded = load_qa_scorecards(path)
    normalized = normalize_revision_input(path)
    assert loaded["schema_version"] == "p50.creative_qa_pack.v1"
    assert normalized["is_valid"] is True
    assert len(normalized["scorecards"]) == 2


def test_revision_tasks_map_low_dimensions_to_actions() -> None:
    scorecard = {
        "pilot_number": 1,
        "pilot_name": "weak-hook",
        "topic": "AI automation",
        "platform": "youtube_shorts",
        "output_dir": "",
        "baseline_scores": {
            "hook_strength": 61,
            "clarity": 88,
            "retention_potential": 64,
            "platform_fit": 90,
            "originality": 84,
            "rights_readiness": 94,
            "monetization_fit": 82,
            "production_feasibility": 90,
        },
        "weighted_overall_score": 73,
        "recommendation": "revise_before_production",
        "top_issues": [],
        "next_actions": [],
    }
    tasks = revision_tasks_for_scorecard(scorecard)
    dimensions = {task["dimension"] for task in tasks}
    assert "hook_strength" in dimensions
    assert "retention_potential" in dimensions
    assert any(task["severity"] == "high" for task in tasks)


def test_build_pilot_revision_pack_includes_patch_and_checks(tmp_path: Path) -> None:
    qa_pack = _qa_pack(tmp_path)
    scorecard = normalize_revision_input(qa_pack)["scorecards"][0]
    pack = build_pilot_revision_pack(scorecard)
    assert pack["revised_brief_patch"]["topic"] == scorecard["topic"]
    assert pack["revision_tasks"]
    assert pack["acceptance_checks"]
    assert pack["human_approval"]["status"] == "pending"


def test_build_revision_plan_contains_summary_and_guardrails(tmp_path: Path) -> None:
    plan = build_revision_plan(_qa_pack(tmp_path))
    assert plan["schema_version"] == "p51.local_revision_plan.v1"
    assert plan["is_valid"] is True
    assert plan["revision_packs"]
    assert plan["batch_revision_summary"]["batch_decision"] in {
        "block_until_critical_revisions_done",
        "revise_then_regenerate_pilot_batch",
        "ready_for_next_generation_after_human_review",
    }
    assert plan["deployment_performed"] is False
    assert plan["rendering_performed"] is False
    assert plan["upload_or_publish_performed"] is False


def test_write_revision_files_creates_local_outputs(tmp_path: Path) -> None:
    qa_result = write_creative_qa_files(run_pilot_batch(DEFAULT_PILOT_BRIEFS[:2], tmp_path / "pilots", overwrite=True), tmp_path / "pilots")
    result = write_revision_files(qa_result, tmp_path / "pilots")
    assert result["is_valid"] is True
    assert Path(result["revision_plan_path"]).exists()
    assert Path(result["revision_summary_path"]).exists()
    assert Path(result["revision_pack_dir"]).exists()
    assert Path(result["revised_brief_patch_dir"]).exists()
    assert result["written_files"]


def test_blocked_scorecard_gets_block_priority() -> None:
    qa_pack = {
        "scorecards": [
            {
                "pilot_number": 1,
                "pilot_name": "blocked-rights",
                "topic": "sample",
                "platform": "youtube_shorts",
                "output_dir": "",
                "baseline_scores": {
                    "hook_strength": 80,
                    "clarity": 80,
                    "retention_potential": 80,
                    "platform_fit": 80,
                    "originality": 40,
                    "rights_readiness": 35,
                    "monetization_fit": 80,
                    "production_feasibility": 90,
                },
                "weighted_overall_score": 66,
                "recommendation": "block",
            }
        ]
    }
    plan = build_revision_plan(qa_pack)
    assert plan["revision_packs"][0]["revision_priority"] == "block"
    assert plan["batch_revision_summary"]["batch_decision"] == "block_until_critical_revisions_done"


def test_example_file_matches_revision_planner() -> None:
    example = json.loads(Path("docs/operations/p51-revision-planner-example.json").read_text(encoding="utf-8"))
    plan = build_revision_plan(example["example_qa_pack"])
    assert plan["is_valid"] is True
    for key, expected in example["guardrails"].items():
        assert plan[key] is expected
