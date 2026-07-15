import json
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "portfolio-brands.staging.json"


def _config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_confirmed_brands_have_complete_august_inventory():
    config = _config()
    active = [brand for brand in config["brands"] if brand["metadata"]["onboarding_status"] == "active"]
    assert {brand["slug"] for brand in active} == {"rawr-nation", "animal-x"}
    assert sum(len(brand["ideas"]) for brand in active) == 48
    assert all(len(brand["ideas"]) == brand["monthly_target"] == 24 for brand in active)

    titles, concepts = set(), set()
    valid_formats = {"vertical_short", "vertical_feature"}
    for brand in active:
        assert sum(idea["format_name"] == "vertical_feature" for idea in brand["ideas"]) == 5
        for idea in brand["ideas"]:
            scheduled = date.fromisoformat(idea["scheduled_for"])
            assert scheduled.year == 2026 and scheduled.month == 8
            assert idea["format_name"] in valid_formats
            assert idea["pillar"] in brand["content_pillars"]
            assert idea["title"] not in titles
            assert idea["concept"] not in concepts
            titles.add(idea["title"])
            concepts.add(idea["concept"])


def test_unverified_brands_remain_blocked_without_invented_inventory():
    blocked = [brand for brand in _config()["brands"] if brand["metadata"]["onboarding_status"] != "active"]
    assert len(blocked) == 5
    assert all(not brand.get("ideas") for brand in blocked)
    assert all(not brand["source_links"] for brand in blocked)


def test_bootstrap_creates_inventory_and_reads_readiness_without_publishing():
    source = (ROOT / "scripts" / "p71_bootstrap_portfolio.py").read_text(encoding="utf-8")
    assert '"/portfolio/content"' in source
    assert '"/portfolio/readiness?month_start=' in source
    assert "inventory_duplicates_skipped" in source
    assert "/publish" not in source


def test_readiness_contract_reports_gap_and_stage_counts():
    service = (ROOT / "src" / "application" / "portfolio_service.py").read_text(encoding="utf-8")
    api = (ROOT / "src" / "operator_api" / "app.py").read_text(encoding="utf-8")
    assert "def month_readiness" in service
    assert '"stage_counts"' in service
    assert 'item["gap"]' in service
    assert 'item["inventory_ready"]' in service
    assert '@app.get("/portfolio/readiness")' in api
    assert '/portfolio/publish' not in api
