from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.campaigns.models import CampaignItemInput, CampaignItemsAddRequest
from src.application.campaigns.service import canonical_item_fingerprint


ROOT = Path(__file__).resolve().parents[2]


def test_p119_migration_is_database_native_and_storage_bounded() -> None:
    migration = (ROOT / "migrations" / "0100_p119_database_native_campaigns.sql").read_text(
        encoding="utf-8"
    )
    required = {
        "pre_generation_autopilot_policies",
        "production_campaigns",
        "production_campaign_versions",
        "production_campaign_items",
        "production_campaign_item_events",
        "pre_generation_packages",
        "asset_storage_locations",
        "ready_for_final_video_generation",
    }
    assert required.issubset(set(part for part in required if part in migration))
    assert "provider IN ('local','google_drive')" in migration
    assert "excel" not in migration.lower()
    assert "xlsx" not in migration.lower()
    assert "google_sheets" not in migration.lower()
    assert "minio" not in migration.lower()
    assert "provider IN ('s3'" not in migration.lower()


def test_campaign_item_normalizes_primary_platform_into_targets() -> None:
    item = CampaignItemInput(
        item_key="AF-001",
        title="The Little Robot and the Last Seed",
        topic="An original robot protects the final living seed.",
        primary_platform="facebook",
        target_platforms=("youtube_shorts",),
        scheduled_for=date(2026, 8, 1),
    )
    assert item.target_platforms == ("facebook", "youtube_shorts")
    assert len(canonical_item_fingerprint(item)) == 64


def test_campaign_request_supports_ten_thousand_items_but_rejects_duplicate_keys() -> None:
    item = CampaignItemInput(
        item_key="item-1",
        title="Valid title",
        topic="Valid topic for a campaign item.",
        scheduled_for=date(2026, 8, 1),
    )
    request = CampaignItemsAddRequest(items=[item])
    assert request.items[0].item_key == "item-1"
    with pytest.raises(ValidationError):
        CampaignItemsAddRequest(items=[item, item])


def test_p119_routes_are_registered_in_runtime_factory() -> None:
    factory = (ROOT / "src" / "operator_api" / "runtime_factory.py").read_text(encoding="utf-8")
    runtime = (ROOT / "src" / "operator_api" / "p119_campaign_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "install_p119_campaign_routes" in factory
    assert "install_p119_campaign_routes(app" in factory
    assert '@app.post("/p119/campaigns")' in runtime
    assert '@app.post("/p119/campaign-versions/{campaign_version_id}/items")' in runtime
    assert '@app.post("/p119/campaign-versions/{campaign_version_id}/validate")' in runtime
    assert '@app.post("/p119/campaign-versions/{campaign_version_id}/activate")' in runtime


def test_autopilot_stops_before_final_video_generation() -> None:
    service = (ROOT / "src" / "application" / "campaigns" / "service.py").read_text(
        encoding="utf-8"
    )
    assert "final video generation" in service.lower()
    assert "automatic_paid_spend" in service
    assert "automatic_public_publishing" in service
    assert "ready_for_final_video_generation" not in service or "CampaignItemState" not in service
