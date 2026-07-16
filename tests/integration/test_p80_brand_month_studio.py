import json
from pathlib import Path

from src.p80_brand_month_studio import build_brand_month_studio


ROOT = Path(__file__).resolve().parents[2]


def test_rawr_month_has_complete_reviewable_packages_without_paid_or_publish_actions() -> None:
    config = json.loads((ROOT / "config/portfolio-brands.staging.json").read_text(encoding="utf-8"))
    result = build_brand_month_studio(config, brand_slug="rawr-nation")
    assert result["summary"] == {
        "masters": 24,
        "facebook_packages": 24,
        "youtube_shorts_packages": 24,
        "tiktok_packages": 24,
        "scripts_ready": 24,
        "batch_one_preview_queue": 6,
        "paid_jobs_started": 0,
        "publish_jobs_started": 0,
    }
    assert len({item["content_fingerprint"] for item in result["items"]}) == 24
    assert all(len(item["scene_plan"]) == 5 for item in result["items"])
    assert all(len(item["platform_packages"]) == 3 for item in result["items"])
    assert all(item["production"]["publish"] == "blocked" for item in result["items"])
    assert all(item["script"]["fact_status"] == "source_ready_pending_human" for item in result["items"][:6])
    assert all(item["script"]["sources"] for item in result["items"][:6])
    assert all(item["script"]["fact_review_required"] for item in result["items"])
