from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p49_pilot_batch_runner import DEFAULT_PILOT_BRIEFS, run_pilot_batch
from src.p50_creative_qa_engine import write_creative_qa_files
from src.p51_revision_planner import write_revision_files
from src.p52_revised_regeneration_runner import (
    apply_revised_brief_patch,
    build_revised_index,
    load_revision_plan,
    normalize_regeneration_input,
    run_revised_regeneration,
)

pytestmark = pytest.mark.integration


def _briefs() -> list[dict]:
    return [dict(item) for item in DEFAULT_PILOT_BRIEFS[:2]]


def _revision_plan(tmp_path: Path) -> dict:
    batch = run_pilot_batch(_briefs(), tmp_path / "pilots", overwrite=True)
    qa = write_creative_qa_files(batch, tmp_path / "pilots")
    revision = write_revision_files(qa, tmp_path / "pilots")
    assert revision["is_valid"] is True
    return revision


def test_normalize_regeneration_input_accepts_briefs_and_revision_plan(tmp_path: Path) -> None:
    revision = _revision_plan(tmp_path)
    normalized = normalize_regeneration_input(_briefs(), revision)
    assert normalized["is_valid"] is True
    assert len(normalized["briefs"]) == 2
    assert len(normalized["revision_packs"]) == revision["pilot_count"]


def test_normalize_regeneration_input_rejects_missing_brief(tmp_path: Path) -> None:
    revision = _revision_plan(tmp_path)
    normalized = normalize_regeneration_input([_briefs()[0]], revision)
    assert normalized["is_valid"] is False
    assert any(item.startswith("missing_original_brief") for item in normalized["validation_errors"])


def test_apply_revised_brief_patch_preserves_core_brief() -> None:
    original = _briefs()[0]
    pack = {
        "pilot_name": original["pilot_name"],
        "revision_priority": "medium",
        "source_recommendation": "revise_before_production",
        "revision_tasks": [{"dimension": "hook_strength"}],
        "revised_brief_patch": {
            "revision_goal": "Make the opening sharper.",
            "hook_direction": "Open with the founder mistake.",
            "script_direction": "Show the workflow in 3 steps.",
            "cta_direction": "Offer checklist after value.",
            "rights_notes": "Use owned mockups.",
            "production_notes": "Use simple screen graphics.",
            "must_add": ["Add a sharp cold-open."],
            "must_avoid": ["Avoid unlicensed screenshots."],
        },
    }
    revised = apply_revised_brief_patch(original, pack)
    assert revised["pilot_name"].endswith("-revised")
    assert revised["topic"] == original["topic"]
    assert revised["platform"] == original["platform"]
    assert "Add a sharp cold-open." in revised["must_use_points"]
    assert revised["human_approval_required_before_production"] is True


def test_run_revised_regeneration_writes_outputs(tmp_path: Path) -> None:
    revision = _revision_plan(tmp_path)
    result = run_revised_regeneration(_briefs(), revision, tmp_path / "revised", overwrite=True)
    assert result["schema_version"] == "p52.revised_pilot_regeneration.v1"
    assert result["is_valid"] is True
    assert result["revised_pilot_count"] == 2
    assert Path(result["revised_pilot_index_path"]).exists()
    assert Path(result["revised_generation_summary_path"]).exists()
    assert Path(result["revised_pilot_briefs_path"]).exists()
    for pilot in result["revised_pilots"]:
        assert Path(pilot["revised_output_dir"]).exists()
        assert Path(pilot["platform_templates_path"]).exists()
        assert pilot["improvement_guaranteed"] is False


def test_revised_index_contains_comparison_fields(tmp_path: Path) -> None:
    revision = _revision_plan(tmp_path)
    result = run_revised_regeneration(_briefs(), revision, tmp_path / "revised", overwrite=True)
    index = json.loads(Path(result["revised_pilot_index_path"]).read_text(encoding="utf-8"))
    assert index["schema_version"] == "p52.revised_pilot_index.v1"
    first = index["revised_pilots"][0]
    for field in [
        "source_pilot_name",
        "revised_pilot_name",
        "revision_priority",
        "applied_patch_count",
        "original_output_dir",
        "revised_output_dir",
        "pipeline_status",
        "engagement_score",
        "monetization_status",
    ]:
        assert field in first


def test_build_revised_index_guardrails() -> None:
    index = build_revised_index([], Path("revised_pilot_briefs.json"))
    assert index["local_only"] is True
    assert index["deployment_performed"] is False
    assert index["upload_or_publish_performed"] is False
    assert index["improvement_guaranteed"] is False
    assert index["human_review_required_before_production"] is True


def test_revision_plan_can_be_loaded_from_path(tmp_path: Path) -> None:
    revision = _revision_plan(tmp_path)
    path = Path(revision["revision_plan_path"])
    loaded = load_revision_plan(path)
    result = run_revised_regeneration(_briefs(), loaded, tmp_path / "revised", overwrite=True)
    assert result["is_valid"] is True


def test_example_file_lists_expected_outputs() -> None:
    example = json.loads(Path("docs/operations/p52-revised-regeneration-example.json").read_text(encoding="utf-8"))
    assert "revised_pilot_index.json" in example["expected_outputs"]
    assert example["guardrails"]["deployment_performed"] is False
