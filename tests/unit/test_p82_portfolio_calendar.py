import json
from collections import Counter
from pathlib import Path

from src.p82_portfolio_calendar import CURRENT_BRANDS, build_portfolio_studio


ROOT = Path(__file__).resolve().parents[2]


def test_four_brand_portfolio_has_complete_unique_30_day_inventory():
    config = json.loads((ROOT / "config/portfolio-brands.staging.json").read_text())
    rawr = json.loads((ROOT / "web/static-creator-ui/data/rawr-nation-month-studio.json").read_text())
    result = build_portfolio_studio(config, rawr)

    assert result["brand_count"] == len(CURRENT_BRANDS) == 4
    assert result["summary"] == {"masters": 480, "platform_exports": 1440, "daily_per_brand": 4, "days": 30}
    for brand in result["brands"]:
        items = brand["items"]
        assert len(items) == len({item["title"] for item in items}) == 120
        assert set(Counter(item["scheduled_for"] for item in items).values()) == {4}
        assert all(len(item["platform_packages"]) == 3 for item in items)
        assert brand["storage_policy"]["database_blobs"] is False
