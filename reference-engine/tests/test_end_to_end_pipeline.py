from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from refintel.models import RightsDeclaration
from refintel.pipeline import ReferencePipeline


def make_fixture(target: Path) -> None:
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
            "testsrc2=size=320x180:rate=24:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=16000:duration=4",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_complete_offline_pipeline(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.mp4"
    make_fixture(fixture)
    pipeline = ReferencePipeline(tmp_path / "workspace")
    ingested = pipeline.ingest_file(
        fixture,
        rights=RightsDeclaration.OWNED,
        title="Synthetic reference",
    )
    processed = pipeline.process(
        ingested.reference_id,
        interval_seconds=1,
        use_local_vision=False,
    )
    workspace = Path(processed.workspace_path)

    assert processed.status.value == "complete"
    assert processed.media is not None
    assert processed.media.width > 0
    assert len(processed.frames) >= 4
    assert (workspace / "media" / "analysis.mp4").stat().st_size > 0
    assert (workspace / "frames" / "contact_sheet.jpg").stat().st_size > 0
    assert (workspace / "reports" / "index.html").stat().st_size > 0
    assert (workspace / "exports" / "reference_fingerprint.json").stat().st_size > 0

    brief_path = pipeline.export_brief(
        processed.reference_id,
        brand_id="rawr_nation",
        topic="An original science story",
        duration_seconds=60,
    )
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    assert brief["brand_id"] == "rawr_nation"
    assert brief["human_review_required"] is True
    assert "exact script wording" in brief["originality_constraints"]


def test_duplicate_file_reuses_reference(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.mp4"
    make_fixture(fixture)
    pipeline = ReferencePipeline(tmp_path / "workspace")
    first = pipeline.ingest_file(fixture, rights=RightsDeclaration.PERMITTED)
    second = pipeline.ingest_file(fixture, rights=RightsDeclaration.PERMITTED)
    assert first.reference_id == second.reference_id
