from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p47_local_folder_runner import (
    build_write_manifest,
    load_brief_json,
    main,
    run_local_folder_export,
    slugify_project_name,
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

EXPECTED_FILES = {
    "producer_brief.md",
    "script.txt",
    "storyboard.md",
    "shot_list.csv",
    "captions.srt",
    "metadata.json",
    "asset_manifest.json",
    "review_checklist.md",
    "platform_variants.json",
    "manifest.json",
    "summary.json",
}


def test_slugify_project_name_is_stable() -> None:
    assert slugify_project_name(VALID_BRIEF) == "ai-automation-for-small-business-owners-youtube-shorts"


def test_load_brief_json_requires_object(tmp_path: Path) -> None:
    path = tmp_path / "brief.json"
    path.write_text(json.dumps(VALID_BRIEF), encoding="utf-8")
    assert load_brief_json(path)["topic"] == VALID_BRIEF["topic"]

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(["not", "object"]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_brief_json(bad)


def test_run_local_folder_export_writes_expected_files(tmp_path: Path) -> None:
    result = run_local_folder_export(VALID_BRIEF, tmp_path)
    assert result["schema_version"] == "p47.local_folder_runner.v1"
    assert result["is_valid"] is True
    output_dir = Path(result["output_dir"])
    assert output_dir.exists()
    assert {item["filename"] for item in result["written_files"]} == EXPECTED_FILES
    for filename in EXPECTED_FILES:
        assert (output_dir / filename).exists()


def test_summary_and_manifest_are_written(tmp_path: Path) -> None:
    result = run_local_folder_export(VALID_BRIEF, tmp_path)
    output_dir = Path(result["output_dir"])
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert summary["local_only"] is True
    assert summary["deployment_performed"] is False
    assert summary["upload_or_publish_performed"] is False
    assert summary["pipeline_status"] in {"ready_for_human_review", "revise", "block"}
    assert {item["filename"] for item in manifest} == EXPECTED_FILES
    assert all(item["local_only"] is True for item in manifest)


def test_invalid_brief_returns_invalid_without_writing(tmp_path: Path) -> None:
    result = run_local_folder_export({"topic": "AI"}, tmp_path)
    assert result["is_valid"] is False
    assert "missing_audience" in result["validation_errors"]
    assert "missing_monetization_goal" in result["validation_errors"]
    assert not any(tmp_path.iterdir())


def test_existing_folder_requires_overwrite(tmp_path: Path) -> None:
    first = run_local_folder_export(VALID_BRIEF, tmp_path)
    assert first["is_valid"] is True
    with pytest.raises(FileExistsError):
        run_local_folder_export(VALID_BRIEF, tmp_path)
    second = run_local_folder_export(VALID_BRIEF, tmp_path, overwrite=True)
    assert second["is_valid"] is True


def test_build_summary_and_manifest_helpers(tmp_path: Path) -> None:
    result = run_local_folder_export(VALID_BRIEF, tmp_path)
    summary = result["summary"]
    assert summary["schema_version"] == "p47.local_export_summary.v1"

    manifest = build_write_manifest({"a.txt": "hello"}, tmp_path)
    assert manifest[0]["filename"] == "a.txt"
    assert manifest[0]["bytes"] == 5


def test_cli_main_writes_folder(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    brief_path = tmp_path / "brief.json"
    output_root = tmp_path / "outputs"
    brief_path.write_text(json.dumps(VALID_BRIEF), encoding="utf-8")
    exit_code = main([str(brief_path), "--output-root", str(output_root)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["ok"] is True
    assert result["file_count"] == len(EXPECTED_FILES)
    assert Path(result["output_dir"]).exists()


def test_cli_main_invalid_json_returns_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    brief_path = tmp_path / "brief.json"
    brief_path.write_text("not-json", encoding="utf-8")
    exit_code = main([str(brief_path), "--output-root", str(tmp_path / "outputs")])
    captured = capsys.readouterr()
    result = json.loads(captured.err)
    assert exit_code == 1
    assert result["ok"] is False


def test_local_only_guardrails(tmp_path: Path) -> None:
    result = run_local_folder_export(VALID_BRIEF, tmp_path)
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["api_server_started"] is False
    assert result["external_calls_performed"] is False
    assert result["rendering_performed"] is False
    assert result["asset_download_performed"] is False
    assert result["upload_or_publish_performed"] is False
