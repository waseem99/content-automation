import json
from pathlib import Path

from src.p54_creator_review_workspace import (
    CREATOR_REVIEW_FILENAME,
    INDEX_FILENAME,
    build_creator_review_workspace,
)


def valid_brief():
    return {
        "topic": "AI automation for service business owners",
        "platform": "youtube_shorts",
        "audience": "small agency founders and service business owners",
        "tone": "clear, high-trust, practical",
        "duration_seconds": 45,
        "monetization_goal": "generate qualified leads for an AI automation consulting offer",
        "must_use_points": [
            "Open with the hidden cost of manual operations.",
            "Show a simple before/after workflow transformation.",
        ],
        "avoid": [
            "Do not use celebrity likeness, brand logos, copied music, or third-party clips.",
        ],
        "source_notes": ["Use owned graphics and original narration only."],
    }


def test_creator_review_workspace_writes_browser_review_files(tmp_path):
    result = build_creator_review_workspace(
        valid_brief(),
        tmp_path,
        project_slug="review-demo",
        overwrite=True,
    )

    assert result["is_valid"] is True
    output_dir = Path(result["output_dir"])
    assert (output_dir / INDEX_FILENAME).exists()
    assert (output_dir / CREATOR_REVIEW_FILENAME).exists()
    assert (output_dir / "producer_brief.md").exists()
    assert (output_dir / "script.txt").exists()
    assert (output_dir / "storyboard.md").exists()
    assert (output_dir / "shot_list.csv").exists()
    assert (output_dir / "captions.srt").exists()

    html = (output_dir / INDEX_FILENAME).read_text(encoding="utf-8")
    assert "Local creator review workspace" in html
    assert "Decision" in html
    assert "Artifact Links" in html
    assert "approve_for_production" in html
    assert "Script Preview" in html

    review = json.loads((output_dir / CREATOR_REVIEW_FILENAME).read_text(encoding="utf-8"))
    assert review["project"]["topic"] == valid_brief()["topic"]
    assert review["reviewer"]["decision_options"] == ["approve_for_production", "revise", "reject"]
    assert review["reviewer"]["human_review_required_before_production"] is True
    assert review["files"]["script.txt"]["exists"] is True


def test_creator_review_workspace_is_local_only(tmp_path):
    result = build_creator_review_workspace(valid_brief(), tmp_path, project_slug="local-only", overwrite=True)

    assert result["is_valid"] is True
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["hosted_ui_created"] is False
    assert result["api_server_started"] is False
    assert result["external_calls_performed"] is False
    assert result["rendering_performed"] is False
    assert result["asset_download_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["monetization_guaranteed"] is False
    assert result["performance_guaranteed"] is False


def test_creator_review_workspace_html_has_no_external_scripts(tmp_path):
    result = build_creator_review_workspace(valid_brief(), tmp_path, project_slug="safe-html", overwrite=True)
    html = Path(result["index_html_path"]).read_text(encoding="utf-8")

    assert "<script" not in html.lower()
    assert "http://" not in html.lower()
    assert "https://" not in html.lower()


def test_creator_review_workspace_invalid_brief_returns_errors(tmp_path):
    result = build_creator_review_workspace(
        {"platform": "youtube_shorts", "audience": "founders"},
        tmp_path,
        project_slug="invalid",
        overwrite=True,
    )

    assert result["is_valid"] is False
    assert "missing_topic" in result["validation_errors"]
    assert "missing_monetization_goal" in result["validation_errors"]
    assert result["deployment_performed"] is False
    assert result["upload_or_publish_performed"] is False


def test_creator_review_workspace_existing_folder_requires_overwrite(tmp_path):
    first = build_creator_review_workspace(valid_brief(), tmp_path, project_slug="duplicate", overwrite=True)
    second = build_creator_review_workspace(valid_brief(), tmp_path, project_slug="duplicate", overwrite=False)

    assert first["is_valid"] is True
    assert second["is_valid"] is False
    assert any("already exists" in error for error in second["validation_errors"])
