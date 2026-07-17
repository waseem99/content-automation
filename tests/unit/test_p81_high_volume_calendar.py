import json
from collections import Counter
from pathlib import Path

from src.p81_high_volume_calendar import build_high_volume_studio


ROOT = Path(__file__).resolve().parents[2]


def test_rawr_calendar_has_four_unique_original_packages_per_day():
    config = json.loads((ROOT / "config/portfolio-brands.staging.json").read_text())
    base = json.loads((ROOT / "web/static-creator-ui/data/rawr-nation-month-studio.json").read_text())
    result = build_high_volume_studio(base, config)

    assert result["summary"]["masters"] == 120
    assert result["summary"]["platform_exports"] == 360
    assert len({item["title"] for item in result["items"]}) == 120
    assert set(Counter(item["scheduled_for"] for item in result["items"]).values()) == {4}
    assert {item["production_tier"] for item in result["items"]} == {"efficient", "hybrid", "premium"}
    assert result["storage_policy"]["database_blobs"] is False
