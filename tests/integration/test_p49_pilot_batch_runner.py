from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.p49_pilot_batch_runner import (
    DEFAULT_PILOT_BRIEFS,
    PLATFORM_TEMPLATE_FILENAME,
    build_pilot_index,
    load_pilot_briefs,
    main,
    render_pilot_review_checklist,
    run_pilot_batch,
    validate_pilot_briefs,
)

pytestmark = pytest.mark.integration


def test_default_pilot_library_has_five_realistic_briefs() -> None:
    assert len(DEFAULT_PILOT_BRIEFS) >= 5
    for brief in DEFAULT_PILOT_BRIEFS:
        assert brief["topic"]
        assert brief["platform"]
        assert brief["audience"]
        assert brief["monetization_goal"]
        assert brief["avoid"]
        assert brief["source_notes"]


def test_load_pilot_briefs_accepts_object_or_list(tmp_path: Path) -> None:
    object_path = tmp_path / "object.json"
    list_path = tmp_path / "list.json"
    object_path.write_text(json.dumps({"briefs": DEFAULT_PILOT_BRIEFS[:2]}), encoding="utf-8")
    list_path.write_text(json.dumps(DEFAULT_PILOT_BRIEFS[:2]), encoding="utf-8")
    assert len(load_pilot_briefs(object_path)) == 2
    assert len(load_pilot_briefs(list_path)) == 2


def test_validate_pilot_briefs_catches_missing_fields() -> None:
    errors = validate_pilot_briefs([{"topic": "Only topic"}])
    assert "pilot_1_missing_platform" in errors
    assert "pilot_1_missing_audience" in errors
    assert "pilot_1_missing_monetization_goal" in errors


def test_run_pilot_batch_writes_pilot_folders_and_templates(tmp_path: Path) -> None:
    result = run_pilot_batch(DEFAULT_PILOT_BRIEFS[:2], tmp_path)
    assert result["schema_version"] == "p49.real_pilot_batch_runner.v1"
    assert result["is_valid"] is True
    assert result["pilot_count"] == 2
    assert result["successful_pilots"] == 2
    assert Path(result["pilot_index_path"]).exists()
    assert Path(result["pilot_review_checklist_path"]).exists()
    for pilot in result["pilots"]:
        output_dir = Path(pilot["output_dir"])
        assert output_dir.exists()
        assert (output_dir / "producer_brief.md").exists()
        assert (output_dir / PLATFORM_TEMPLATE_FILENAME).exists()
        template_pack = json.loads((output_dir / PLATFORM_TEMPLATE_FILENAME).read_text(encoding="utf-8"))
        assert template_pack["schema_version"] == "p48.platform_template_pack.v1"
        assert {"youtube_shorts", "instagram_reels", "tiktok", "youtube_long", "carousel_newsletter"}.issubset(template_pack["templates"])


def test_manifest_includes_platform_templates(tmp_path: Path) -> None:
    result = run_pilot_batch(DEFAULT_PILOT_BRIEFS[:1], tmp_path)
    output_dir = Path(result["pilots"][0]["output_dir"])
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert PLATFORM_TEMPLATE_FILENAME in {item["filename"] for item in manifest}


def test_batch_index_and_review_checklist_helpers() -> None:
    pilots = [
        {
            "pilot_number": 1,
            "pilot_name": "sample",
            "topic": "Sample topic",
            "platform": "youtube_shorts",
            "is_valid": True,
            "output_dir": "/tmp/sample",
            "pipeline_status": "revise",
            "rights_gate": "revise",
            "engagement_score": 80,
            "monetization_status": "needs_packaging_improvement",
            "next_actions": ["Review hook"],
            "file_count": 12,
        }
    ]
    index = build_pilot_index(pilots)
    checklist = render_pilot_review_checklist(pilots)
    assert index["pilot_count"] == 1
    assert index["local_only"] is True
    assert "Pilot 1" in checklist
    assert "Hook is strong enough" in checklist


def test_invalid_batch_returns_without_writing(tmp_path: Path) -> None:
    result = run_pilot_batch([], tmp_path)
    assert result["is_valid"] is False
    assert "missing_pilot_briefs" in result["validation_errors"]
    assert not tmp_path.exists() or not any(tmp_path.iterdir())


def test_cli_main_runs_with_example_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pilot_path = tmp_path / "pilots.json"
    output_root = tmp_path / "pilot_outputs"
    pilot_path.write_text(json.dumps({"briefs": DEFAULT_PILOT_BRIEFS[:1]}), encoding="utf-8")
    exit_code = main([str(pilot_path), "--output-root", str(output_root)])
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 0
    assert result["ok"] is True
    assert result["pilot_count"] == 1
    assert Path(result["pilot_index_path"]).exists()


def test_guardrails_remain_local_only(tmp_path: Path) -> None:
    result = run_pilot_batch(DEFAULT_PILOT_BRIEFS[:1], tmp_path)
    assert result["local_only"] is True
    assert result["deployment_performed"] is False
    assert result["api_server_started"] is False
    assert result["trend_scraping_performed"] is False
    assert result["platform_api_called"] is False
    assert result["rendering_performed"] is False
    assert result["asset_download_performed"] is False
    assert result["upload_or_publish_performed"] is False
    assert result["performance_guaranteed"] is False
