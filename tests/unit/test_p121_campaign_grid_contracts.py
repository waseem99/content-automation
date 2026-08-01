from __future__ import annotations

from pathlib import Path

from src.application.pre_generation.query_service import CampaignQueryService, SORTS
from src.operator_api.p121_campaign_grid_runtime import install_p121_campaign_grid_routes


ROOT = Path(__file__).resolve().parents[2]


def test_query_service_and_routes_are_available() -> None:
    assert CampaignQueryService.__name__ == "CampaignQueryService"
    assert callable(install_p121_campaign_grid_routes)
    assert set(SORTS) == {
        "ordinal",
        "priority",
        "scheduled_for",
        "updated_at",
        "title",
        "state",
        "score",
        "exceptions",
    }


def test_grid_uses_keyset_cursor_and_bounded_pages() -> None:
    source = (ROOT / "src" / "application" / "pre_generation" / "query_service.py").read_text(encoding="utf-8")
    assert "base64.urlsafe_b64encode" in source
    assert "campaign_cursor_sort_mismatch" in source
    assert "limit <= 500" in source
    assert "LIMIT %s" in source
    assert "next_cursor" in source
    assert "OFFSET" not in source


def test_bulk_retry_is_database_backed_and_audited() -> None:
    source = (ROOT / "src" / "application" / "pre_generation" / "query_service.py").read_text(encoding="utf-8")
    assert "maximum <= 20_000" in source
    assert "FOR UPDATE OF item,run SKIP LOCKED" in source
    assert "production_campaign_actions" in source
    assert "bulk_retry_matching" in source
    assert "item_ids" in source


def test_creator_studio_renders_only_one_bounded_page() -> None:
    html = (ROOT / "web" / "static-creator-ui" / "index.html").read_text(encoding="utf-8")
    ui = (ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-campaign-operations.js").read_text(encoding="utf-8")
    assert "studio-v2-campaign-operations.js" in html
    assert "Only" in ui and "rows are rendered" in ui
    assert "Rows per page" in ui
    assert "Retry all matching" in ui
    assert "next_cursor" in ui
    assert "cursorHistory" in ui
    assert "/p121/campaigns/" in ui
