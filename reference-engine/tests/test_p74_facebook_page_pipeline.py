from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from refintel.facebook import (
    canonical_video_url,
    export_netscape_cookies,
    page_discovery_urls,
    save_discovery,
    validate_facebook_page_url,
)
from refintel.frame_stream import analyze_every_frame


class FakeContext:
    def cookies(self, _url: str):
        return [
            {
                "domain": ".facebook.com",
                "path": "/",
                "secure": True,
                "expires": 1_900_000_000,
                "name": "operator_session",
                "value": "sensitive-value",
            }
        ]


def test_stable_page_urls_are_accepted_and_share_redirects_are_rejected():
    assert validate_facebook_page_url("https://www.facebook.com/RawrNationTV")
    assert validate_facebook_page_url(
        "https://www.facebook.com/profile.php?id=61580906280508"
    )
    with pytest.raises(ValueError, match="share redirect"):
        validate_facebook_page_url("https://www.facebook.com/share/temporary/")
    with pytest.raises(ValueError, match="facebook.com"):
        validate_facebook_page_url("https://example.com/page")


def test_page_discovery_targets_handle_and_page_id_tabs():
    handle = page_discovery_urls("https://www.facebook.com/RawrNationTV")
    assert handle == [
        "https://www.facebook.com/RawrNationTV",
        "https://www.facebook.com/RawrNationTV/reels",
        "https://www.facebook.com/RawrNationTV/videos",
    ]
    page_id = page_discovery_urls(
        "https://www.facebook.com/profile.php?id=61563298430902"
    )
    assert page_id[-2].endswith("id=61563298430902&sk=reels_tab")
    assert page_id[-1].endswith("id=61563298430902&sk=videos")


def test_discovered_video_urls_are_canonical_and_tracking_free():
    assert canonical_video_url(
        "https://www.facebook.com/RawrNationTV/videos/12345/?mibextid=tracking"
    ) == "https://www.facebook.com/RawrNationTV/videos/12345"
    assert canonical_video_url(
        "https://www.facebook.com/reel/98765/?s=single_unit"
    ) == "https://www.facebook.com/reel/98765"
    assert canonical_video_url(
        "https://www.facebook.com/watch/?v=555&tracking=yes"
    ) == "https://www.facebook.com/watch?v=555"
    assert canonical_video_url("https://www.facebook.com/RawrNationTV") is None


def test_cookie_jar_is_private_and_never_saved_in_discovery_manifest(tmp_path: Path):
    cookie_file = export_netscape_cookies(FakeContext(), tmp_path / "facebook-cookies.txt")
    content = cookie_file.read_text(encoding="utf-8")
    assert content.startswith("# Netscape HTTP Cookie File")
    assert "operator_session" in content
    if os.name != "nt":
        assert cookie_file.stat().st_mode & 0o777 == 0o600

    manifest = tmp_path / "discovery.json"
    save_discovery(
        {
            "page_url": "https://www.facebook.com/RawrNationTV",
            "entry_count": 0,
            "entries": [],
            "cookie_file": str(cookie_file),
        },
        manifest,
    )
    saved = json.loads(manifest.read_text(encoding="utf-8"))
    assert "cookie_file" not in saved
    assert "sensitive-value" not in manifest.read_text(encoding="utf-8")


def test_pipeline_contract_enables_every_frame_and_sequence_analysis():
    root = Path(__file__).resolve().parents[1]
    repository = root.parent
    pipeline = (root / "refintel" / "pipeline.py").read_text(encoding="utf-8")
    analysis = (root / "refintel" / "analysis.py").read_text(encoding="utf-8")
    fingerprint = (root / "refintel" / "fingerprint.py").read_text(encoding="utf-8")
    facebook = (root / "refintel" / "facebook.py").read_text(encoding="utf-8")
    portfolio_runner = (
        repository / "scripts" / "p74_run_facebook_portfolio.py"
    ).read_text(encoding="utf-8")
    assert "analyze_every_frame(proxy_path, workspace)" in pipeline
    assert "def analyze_sequence(" in analysis
    assert "source_specific_elements_to_avoid" in analysis
    assert "Sequence observation for human review" in fingerprint
    assert "cookie_path_persisted_in_manifest" in facebook
    assert "every_frame=True" in facebook
    assert "active_research_pending" in portfolio_runner
    assert "run_facebook_page_batch" in portfolio_runner


def test_every_frame_analyzer_decodes_complete_short_fixture(tmp_path: Path):
    pytest.importorskip("cv2")
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not installed")
    video = tmp_path / "ten-frames.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=10:duration=1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    payload = analyze_every_frame(video, tmp_path / "workspace")
    assert payload["frame_count"] == 10
    assert len(payload["frames"]) == 10
    assert payload["fps"] == 10
    assert (tmp_path / "workspace" / "frames" / "every_frame_metrics.json").is_file()
