from __future__ import annotations

from pathlib import Path

from src.application.pre_generation.service import RULE_VERSION
from src.application.pre_generation.validated_service import ValidatedPreGenerationService
from src.application.campaign_storage.google_drive import GoogleDriveStorage
from src.application.campaign_storage.service import CampaignStorageService
from src.operator_api.p120_pre_generation_runtime import install_p120_pre_generation_routes
from src.operator_api.p120_storage_runtime import install_p120_storage_routes


ROOT = Path(__file__).resolve().parents[2]


def test_rule_and_services_are_importable() -> None:
    assert RULE_VERSION == "p120-v1"
    assert ValidatedPreGenerationService.__name__ == "ValidatedPreGenerationService"
    assert CampaignStorageService.__name__ == "CampaignStorageService"
    assert callable(install_p120_pre_generation_routes)
    assert callable(install_p120_storage_routes)


def test_google_drive_adapter_is_off_by_default() -> None:
    drive = GoogleDriveStorage(
        access_token="",
        refresh_token="",
        client_id="",
        client_secret="",
        root_folder_id="",
    )
    assert drive.configured is False
    assert drive.renewable is False


def test_google_drive_supports_renewable_oauth_without_database_credentials() -> None:
    source = (ROOT / "src" / "application" / "campaign_storage" / "google_drive.py").read_text(encoding="utf-8")
    environment = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")
    assert "https://oauth2.googleapis.com/token" in source
    assert '"grant_type": "refresh_token"' in source
    assert "GOOGLE_DRIVE_CLIENT_ID=" in environment
    assert "GOOGLE_DRIVE_CLIENT_SECRET=" in environment
    assert "GOOGLE_DRIVE_REFRESH_TOKEN=" in environment
    assert "Credentials remain environment-only" in source


def test_migration_defines_durable_autopilot_and_grouped_exceptions() -> None:
    migration = (ROOT / "migrations" / "0101_p120_pre_generation_autopilot.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE football_brief.pre_generation_runs" in migration
    assert "FOR UPDATE" not in migration  # runtime claims use SKIP LOCKED; migration remains declarative
    assert "CREATE TABLE football_brief.pre_generation_checks" in migration
    assert "CREATE TABLE football_brief.pre_generation_exceptions" in migration
    assert "CREATE TABLE football_brief.production_campaign_actions" in migration
    assert "CREATE TABLE football_brief.asset_storage_reconciliation_runs" in migration
    # The terminal state already exists in migration 0100. Migration 0101 may
    # document it, but must not redefine the production-campaign item schema.
    assert "ALTER TABLE football_brief.production_campaign_items" not in migration
    assert "ADD COLUMN state" not in migration


def test_worker_uses_database_leases_and_skip_locked() -> None:
    service = (ROOT / "src" / "application" / "pre_generation" / "service.py").read_text(encoding="utf-8")
    patch = (ROOT / "src" / "application" / "pre_generation" / "runtime_patch.py").read_text(encoding="utf-8")
    worker = (ROOT / "src" / "operations" / "pre_generation_worker.py").read_text(encoding="utf-8")
    assert "FOR UPDATE OF run SKIP LOCKED" in service
    assert "%s::text" in patch
    assert "lease_token" in service
    assert "ThreadPoolExecutor" in worker
    assert "PRE_GENERATION_CONCURRENCY" in worker


def test_renderer_ready_package_is_frozen_before_generation() -> None:
    service = (ROOT / "src" / "application" / "pre_generation" / "service.py").read_text(encoding="utf-8")
    patch = (ROOT / "src" / "application" / "pre_generation" / "runtime_patch.py").read_text(encoding="utf-8")
    assert "ready-for-final-video-generation/v1" in service
    assert '"shots": _renderer_shots' in patch
    assert '"negative_prompt"' in patch
    assert '"continuity_bindings"' in patch
    assert '"segments"' in patch
    assert '"outputs": outputs' in patch
    assert "correction_count=correction_count+1" in patch
    assert "unassigned_hybrid_router" in patch


def test_product_boundaries_are_explicit() -> None:
    service = (ROOT / "src" / "application" / "pre_generation" / "service.py").read_text(encoding="utf-8")
    storage = (ROOT / "src" / "application" / "campaign_storage" / "service.py").read_text(encoding="utf-8")
    migration = (ROOT / "migrations" / "0100_p119_database_native_campaigns.sql").read_text(encoding="utf-8")
    assert '"automatic_paid_spend": False' in service
    assert '"automatic_public_publishing": False' in service
    assert '"final_video_generation_deferred": True' in service
    assert "provider IN ('local','google_drive')" in migration
    forbidden = ("google_sheets", "xlsx", "minio", "s3://")
    combined = f"{service}\n{storage}".lower()
    assert not any(value in combined for value in forbidden)


def test_creator_studio_has_native_campaign_route() -> None:
    html = (ROOT / "web" / "static-creator-ui" / "index.html").read_text(encoding="utf-8")
    javascript = (ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-campaigns.js").read_text(encoding="utf-8")
    assert "studio-v2-campaigns.js" in html
    assert 'const routeRoot = "/app/campaigns"' in javascript
    assert "Create, activate and start autopilot" in javascript
    assert "Final video generation is not connected" in javascript


def test_windows_deployment_keeps_p120_worker_on_current_schema_head() -> None:
    environment = (ROOT / "config" / "local.env.example").read_text(encoding="utf-8")
    deploy = (ROOT / "scripts" / "windows" / "deploy_always_on_local_production.ps1").read_text(encoding="utf-8")
    remote = (ROOT / "scripts" / "windows" / "deploy_remote_content_automation.ps1").read_text(encoding="utf-8")
    sync = (ROOT / "scripts" / "windows" / "sync_p131_environment.ps1").read_text(encoding="utf-8")
    task = (ROOT / "scripts" / "windows" / "install_pre_generation_service.ps1").read_text(encoding="utf-8")
    assert "OPS_MIGRATION_HEAD=0108_p131_staged_acceptance_closeout.sql" in environment
    assert "PRE_GENERATION_AUTOPILOT_ENABLED=true" in environment
    assert "install_pre_generation_service.ps1" in deploy
    assert "sync_p131_environment.ps1" in deploy
    assert "0108_p131_staged_acceptance_closeout.sql" in remote
    assert "0108_p131_staged_acceptance_closeout.sql" in sync
    assert "New-ScheduledTask" in task
