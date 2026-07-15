from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "operations" / "p68-step-02.md"
MATRIX = ROOT / "reference-engine" / "pilots" / "p68-cross-platform-acceptance.json"


def test_p68_step_02_has_cross_platform_matrix_and_honest_evidence_status() -> None:
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    rows = {item["platform"]: item for item in payload["platforms"]}
    assert set(rows) == {"facebook", "youtube", "instagram", "tiktok", "x"}
    assert rows["facebook"]["evidence"] == "P67 workflow run 29146959999"
    assert rows["facebook"]["live_status"] == "validated_direct_reel"
    assert all(
        rows[name]["live_status"] == "operator_reference_required"
        for name in ("youtube", "instagram", "tiktok", "x")
    )
    assert payload["source_media_policy"] == (
        "temporary-local-analysis-only-do-not-commit-or-republish"
    )


def test_p68_step_02_implements_direct_url_validation_and_adaptive_sampling() -> None:
    ingest = (ROOT / "reference-engine" / "refintel" / "ingest.py").read_text(
        encoding="utf-8"
    )
    acquisition = (
        ROOT / "reference-engine" / "refintel" / "acquisition.py"
    ).read_text(encoding="utf-8")
    media = (ROOT / "reference-engine" / "refintel" / "media.py").read_text(
        encoding="utf-8"
    )
    pipeline = (ROOT / "reference-engine" / "refintel" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "validate_direct_video_url" in ingest
    assert "profile/page URLs are not direct video inputs" in ingest
    assert "AcquisitionService().acquire(" in ingest
    assert 'options["cookiesfrombrowser"]' in acquisition
    assert "cookie paths" not in acquisition.lower()
    assert "adaptive_interval_seconds" in media
    assert 'return 60\n\n\ndef resolve_interval_seconds' in media
    assert '"mode": sampling_mode' in pipeline
    assert '"interval_seconds": resolved_interval' in pipeline


def test_p68_step_02_documentation_preserves_access_and_originality_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #714. Closes #716 after the PR merges.",
        "Facebook has one real direct-reel success",
        "operator-supplied authorized public example",
        "must not claim that a platform has passed live acceptance",
        "Record the exact extractor failure.",
        "Do not bypass access controls.",
        "cookies, and session data are never stored",
        "2 seconds",
        "3 seconds",
        "5 seconds",
        "10 seconds",
        "30 seconds",
        "60 seconds",
        "Scene detection runs separately",
        "crawl platform profiles or pages",
        "upload or log cookies",
        "republish source media",
        "generate or stitch production clips",
        "P68-03 remains responsible",
    ]:
        assert term in content
