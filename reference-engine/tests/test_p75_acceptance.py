import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cross_platform_acceptance_matrix_is_complete_and_honest() -> None:
    matrix = json.loads(
        (ROOT / "pilots" / "p75-cross-platform-acceptance.json").read_text()
    )
    platforms = {item["platform"]: item for item in matrix["platforms"]}
    assert set(platforms) == {
        "youtube", "instagram", "tiktok", "x", "facebook", "snapchat", "local"
    }
    assert platforms["snapchat"]["profile_discovery"] == "unsupported"
    assert platforms["facebook"]["live_probe"] == (
        "controlled-public-probe-in-p67-workflow"
    )
    assert all(item["fallback"] for item in platforms.values())
    assert matrix["execution_profiles"] == ["cpu", "gpu", "low-memory"]
    assert matrix["per_item_failure_isolation"] is True
    assert matrix["source_media_in_acceptance_artifacts"] is False
    assert matrix["automatic_publication"] is False
    assert matrix["human_review_required"] is True


def test_acceptance_matrix_contains_no_credentials_or_source_urls() -> None:
    rendered = (ROOT / "pilots" / "p75-cross-platform-acceptance.json").read_text()
    for forbidden in ("password=", "token=", "cookie=", "facebook.com/", "youtube.com/"):
        assert forbidden not in rendered.lower()
