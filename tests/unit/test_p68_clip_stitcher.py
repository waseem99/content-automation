from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.p68_clip_stitcher import (
    assemble_clip_plan,
    transition_schedule,
    validate_clip_manifest,
)


def plan() -> dict[str, object]:
    return {
        "schema_version": "p68.original_continuity_plan.v1",
        "shots": [
            {
                "shot_id": "S01",
                "duration_seconds": 1.0,
                "transition_handle_seconds": 0.5,
                "transition_in": {"strategy": "cold_open"},
            },
            {
                "shot_id": "S02",
                "duration_seconds": 1.0,
                "transition_handle_seconds": 0.5,
                "transition_in": {"strategy": "j_cut"},
            },
        ],
    }


def make_clip(path: Path, color: str, frequency: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not installed")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:size=180x320:rate=24:duration=1.7",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration=1.7",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
        timeout=60,
    )


def manifest(first: Path, second: Path) -> dict[str, object]:
    return {
        "clips": [
            {
                "shot_id": "S01",
                "path": str(first),
                "provider": "synthetic-test-fixture",
                "prompt_or_asset_reference": "fixture-red",
                "rights_status": "owned",
                "human_review_status": "approved_for_assembly",
            },
            {
                "shot_id": "S02",
                "path": str(second),
                "provider": "synthetic-test-fixture",
                "prompt_or_asset_reference": "fixture-blue",
                "rights_status": "owned",
                "human_review_status": "approved_for_assembly",
            },
        ]
    }


def test_manifest_requires_exact_order_lineage_rights_and_human_status(tmp_path: Path) -> None:
    first, second = tmp_path / "first.mp4", tmp_path / "second.mp4"
    first.touch()
    second.touch()
    payload = manifest(first, second)
    payload["clips"].reverse()
    payload["clips"][0]["provider"] = ""
    payload["clips"][0]["rights_status"] = "unknown"
    errors = validate_clip_manifest(plan(), payload)
    assert "clip_order_must_exactly_match_planned_shot_order" in errors
    assert "S02:provider_lineage_required" in errors
    assert "S02:rights_status_not_accepted" in errors


def test_transition_schedule_records_j_cut_audio_lead() -> None:
    schedule = transition_schedule(plan())
    assert schedule[0]["visual_transition"] == "cold_open"
    assert schedule[1]["visual_transition"] == "j_cut"
    assert "lead the picture cut" in schedule[1]["audio_bridge"]
    assert all(item["story_motivated"] for item in schedule)


def test_real_ffmpeg_normalize_stitch_mix_and_probe(tmp_path: Path) -> None:
    first, second = tmp_path / "first.mp4", tmp_path / "second.mp4"
    make_clip(first, "red", 330)
    make_clip(second, "blue", 550)
    result = assemble_clip_plan(plan(), manifest(first, second), tmp_path / "output")
    output = Path(result["output_path"])

    assert result["is_valid"] is True
    assert output.stat().st_size > 0
    assert result["probe"]["width"] == 1080
    assert result["probe"]["height"] == 1920
    assert result["probe"]["video_codec"] == "h264"
    assert result["probe"]["audio_codec"] == "aac"
    assert result["probe"]["sample_rate"] == 48000
    assert result["probe"]["channels"] == 2
    assert result["quality_approved"] is False
    assert result["publish_allowed"] is False
    assert (tmp_path / "output" / "render_manifest.json").is_file()
