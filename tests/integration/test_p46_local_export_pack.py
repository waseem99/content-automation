from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from src.p45_video_pipeline_orchestrator import run_video_content_pipeline
from src.p46_local_export_pack import (
    build_artifact_manifest,
    build_local_export_pack,
    render_captions_srt,
    render_shot_list_csv,
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
}


def test_export_pack_accepts_raw_brief() -> None:
    pack = build_local_export_pack(VALID_BRIEF)
    assert pack["schema_version"] == "p46.local_producer_export_pack.v1"
    assert pack["is_valid"] is True
    assert set(pack["files"]) == EXPECTED_FILES
    assert len(pack["artifact_manifest"]) == len(EXPECTED_FILES)


def test_export_pack_accepts_p45_pipeline_package() -> None:
    pipeline = run_video_content_pipeline(VALID_BRIEF)
    pack = build_local_export_pack(pipeline)
    assert pack["is_valid"] is True
    assert pack["pipeline_package"]["schema_version"] == "p45.end_to_end_video_pipeline.v1"
    assert "Producer Brief" in pack["files"]["producer_brief.md"]


def test_invalid_brief_fails_cleanly() -> None:
    pack = build_local_export_pack({"topic": "AI"})
    assert pack["is_valid"] is False
    assert "missing_audience" in pack["validation_errors"]
    assert pack["deployment_performed"] is False


def test_shot_list_csv_is_parseable() -> None:
    pipeline = run_video_content_pipeline(VALID_BRIEF)
    csv_text = render_shot_list_csv(pipeline)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert rows
    assert "shot_id" in rows[0]
    assert "editor_note" in rows[0]


def test_captions_are_srt_ready() -> None:
    pipeline = run_video_content_pipeline(VALID_BRIEF)
    srt = render_captions_srt(pipeline)
    assert "00:00:" in srt
    assert "-->" in srt
    assert srt.splitlines()[0] == "1"


def test_json_artifacts_are_parseable() -> None:
    pack = build_local_export_pack(VALID_BRIEF)
    json.loads(pack["files"]["metadata.json"])
    json.loads(pack["files"]["asset_manifest.json"])
    json.loads(pack["files"]["platform_variants.json"])


def test_manifest_marks_local_only() -> None:
    manifest = build_artifact_manifest({"script.txt": "hello"})
    assert manifest[0]["filename"] == "script.txt"
    assert manifest[0]["content_type"] == "text/plain"
    assert manifest[0]["local_only"] is True


def test_export_guardrails() -> None:
    pack = build_local_export_pack(VALID_BRIEF)
    assert pack["local_only"] is True
    assert pack["deployment_performed"] is False
    assert pack["external_calls_performed"] is False
    assert pack["rendering_performed"] is False
    assert pack["asset_download_performed"] is False
    assert pack["upload_or_publish_performed"] is False


def test_example_file_matches_export_pack() -> None:
    example = json.loads(Path("docs/operations/p46-local-export-example.json").read_text(encoding="utf-8"))
    pack = build_local_export_pack(example["example_brief"])
    for filename in example["expected_files"]:
        assert filename in pack["files"]
    for key, expected in example["guardrails"].items():
        assert pack[key] is expected
