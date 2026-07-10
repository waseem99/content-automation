import json
from pathlib import Path

from src.p61_single_brief_cycle_runner import run_single_brief_cycle


def sample_brief() -> dict:
    return {
        "demo_id": "local-ai-audit-short",
        "topic": "AI audit checklist for agency founders",
        "platform": "youtube_shorts",
        "audience": "agency founders with manual client operations",
        "tone": "practical, direct, founder-led",
        "duration_seconds": 45,
        "content_format": "vertical_short",
        "monetization_goal": "generate qualified leads for an AI operations audit",
        "must_use_points": [
            "Open with the cost of manual follow-up.",
            "Show a simple before and after workflow.",
            "End with a checklist CTA.",
        ],
        "avoid": [
            "Do not promise guaranteed revenue.",
            "Do not use third-party copyrighted assets.",
        ],
        "source_notes": [
            "Use original narration and owned diagrams only."
        ],
    }


def test_run_single_brief_cycle_writes_adapter_and_review_outputs(tmp_path: Path) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(sample_brief()), encoding="utf-8")

    result = run_single_brief_cycle(brief_path, tmp_path / "cycle", overwrite=True)

    assert result["is_valid"] is True
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["human_review_required_before_production"] is True

    assert Path(result["single_brief_cycle_index_path"]).exists()
    assert Path(result["single_brief_cycle_summary_path"]).exists()
    assert Path(result["single_brief_cycle_report_path"]).exists()
    assert Path(result["custom_brief_library_path"]).exists()
    assert Path(result["custom_feedback_template_path"]).exists()
    assert Path(result["review_cycle_index_path"]).exists()

    summary = json.loads(Path(result["single_brief_cycle_summary_path"]).read_text(encoding="utf-8"))
    assert summary["schema_version"] == "p61.single_brief_full_review_cycle.v1"
    assert summary["cycle_status"] == "ready_for_human_review"
    assert summary["counts"]["demo_count"] == 1
    assert "review_cycle_index" in summary["relative_links"]
    assert summary["automated_final_approval"] is False

    html = Path(result["single_brief_cycle_index_path"]).read_text(encoding="utf-8")
    assert "Single Brief Content Review Cycle" in html
    assert "Full Review Cycle" in html
    assert "Human review required" in html


def test_invalid_single_brief_cycle_fails_before_review_cycle(tmp_path: Path) -> None:
    bad_brief = {"topic": "Missing platform and audience"}

    result = run_single_brief_cycle(bad_brief, tmp_path / "bad-cycle", overwrite=True)

    assert result["is_valid"] is False
    assert result["failed_step"] == "custom_brief_adapter"
    assert "missing_platform" in result["validation_errors"]
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False


def test_single_brief_cycle_report_contains_review_guidance(tmp_path: Path) -> None:
    result = run_single_brief_cycle(sample_brief(), tmp_path / "cycle-report", overwrite=True)

    report = Path(result["single_brief_cycle_report_path"]).read_text(encoding="utf-8")
    assert "Replace placeholder feedback with real human review notes" in report
    assert "Do not upload, publish, or produce final video" in report
