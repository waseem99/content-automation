from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from refintel.ingest import validate_direct_video_url, validate_local_cookie_browser
from refintel.media import adaptive_interval_seconds, resolve_interval_seconds
from refintel.models import Platform
from refintel.pipeline import ReferencePipeline


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.facebook.com/reel/865258312526732", Platform.FACEBOOK),
        ("https://www.facebook.com/watch?v=123456", Platform.FACEBOOK),
        ("https://fb.watch/abc123/", Platform.FACEBOOK),
        ("https://www.youtube.com/watch?v=abc123", Platform.YOUTUBE),
        ("https://www.youtube.com/shorts/abc123", Platform.YOUTUBE),
        ("https://youtu.be/abc123", Platform.YOUTUBE),
        ("https://www.instagram.com/reel/abc123/", Platform.INSTAGRAM),
        ("https://www.instagram.com/p/abc123/", Platform.INSTAGRAM),
        ("https://www.tiktok.com/@creator/video/123456", Platform.TIKTOK),
        ("https://x.com/creator/status/123456", Platform.X),
        ("https://twitter.com/creator/status/123456", Platform.X),
    ],
)
def test_direct_video_urls_are_accepted(url: str, platform: Platform) -> None:
    assert validate_direct_video_url(url) == platform


@pytest.mark.parametrize(
    "url",
    [
        "https://www.facebook.com/RawrNationTV",
        "https://www.instagram.com/creator/",
        "https://www.youtube.com/@creator",
        "https://www.tiktok.com/@creator",
        "https://x.com/creator",
        "https://example.com/video/123",
    ],
)
def test_profile_page_and_unknown_urls_are_rejected_with_file_fallback(url: str) -> None:
    with pytest.raises(ValueError, match="direct|Direct|ingest-file"):
        validate_direct_video_url(url)


def test_adaptive_sampling_preserves_short_form_density_and_long_form_minutes() -> None:
    assert adaptive_interval_seconds(12) == 2
    assert adaptive_interval_seconds(30) == 3
    assert adaptive_interval_seconds(60) == 5
    assert adaptive_interval_seconds(120) == 10
    assert adaptive_interval_seconds(300) == 30
    assert adaptive_interval_seconds(601) == 60
    assert resolve_interval_seconds(30, None) == (3, "adaptive")
    assert resolve_interval_seconds(30, 7) == (7, "fixed")
    with pytest.raises(ValueError):
        resolve_interval_seconds(30, 0)


def test_local_cookie_browser_allowlist_does_not_accept_paths_or_profiles() -> None:
    assert validate_local_cookie_browser(None) is None
    assert validate_local_cookie_browser(" Chrome ") == "chrome"
    with pytest.raises(ValueError):
        validate_local_cookie_browser("/home/operator/browser-profile")


def test_pipeline_forwards_browser_cookie_option_only_to_url_ingestion(tmp_path: Path) -> None:
    pipeline = ReferencePipeline(tmp_path)
    pipeline.ingestion.ingest_url = Mock(return_value="url-project")
    pipeline.ingestion.ingest_file = Mock(return_value="file-project")

    url_result = pipeline.ingest_url(
        "https://www.youtube.com/watch?v=abc123",
        rights="owned",
        cookies_from_browser="firefox",
    )
    file_result = pipeline.ingest_file(tmp_path / "authorized.mp4", rights="owned")

    assert url_result == "url-project"
    assert file_result == "file-project"
    pipeline.ingestion.ingest_url.assert_called_once_with(
        "https://www.youtube.com/watch?v=abc123",
        rights="owned",
        title=None,
        operator_note=None,
        cookies_from_browser="firefox",
        force_new=False,
    )
    pipeline.ingestion.ingest_file.assert_called_once_with(
        tmp_path / "authorized.mp4",
        rights="owned",
        title=None,
        operator_note=None,
        force_new=False,
    )


def test_cross_platform_acceptance_matrix_is_honest_about_live_status() -> None:
    path = Path(__file__).resolve().parents[1] / "pilots" / "p68-cross-platform-acceptance.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    platforms = {item["platform"]: item for item in payload["platforms"]}
    assert set(platforms) == {"facebook", "youtube", "instagram", "tiktok", "x"}
    assert platforms["facebook"]["live_status"] == "validated_direct_reel"
    for platform in ("youtube", "instagram", "tiktok", "x"):
        assert platforms[platform]["live_status"] == "operator_reference_required"
        assert platforms[platform]["evidence"] is None
    assert "cookie_upload_or_logging" in payload["prohibited"]
    assert payload["human_review_required"] is True
