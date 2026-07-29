from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.application.scripts.automatic_evidence import AutomaticScriptEvidenceService
from src.operator_api.p110_runtime import (
    ALL_PLATFORMS,
    PLATFORM_PROFILES,
    P110CreateContentRequest,
    P110Error,
    _assert_public_https_url,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "0093_p110_four_brand_multiplatform.sql"
FAMILY_MIGRATION = ROOT / "migrations" / "0094_p110_content_family_defaults.sql"
OVERRIDE_MIGRATION = ROOT / "migrations" / "0095_p111_super_admin_evidence_override.sql"
ONBOARDING = ROOT / "src" / "operations" / "local_onboarding.py"
ONBOARDING_V2 = ROOT / "src" / "operations" / "local_onboarding_v2.py"
WORKER = ROOT / "src" / "operations" / "local_worker_aligned.py"
RUNTIME = ROOT / "src" / "operator_api" / "p110_runtime.py"
PATCH = ROOT / "src" / "operator_api" / "p111_runtime_patch.py"
API = ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-api.js"
UI = ROOT / "web" / "static-creator-ui" / "assets" / "studio-v2-p110.js"
INDEX = ROOT / "web" / "static-creator-ui" / "index.html"
DEPLOY = ROOT / "scripts" / "windows" / "deploy_remote_content_automation.ps1"
CONFIG = ROOT / "config" / "local.env.example"


def request_payload(**overrides):
    value = {
        "brand_id": "00000000-0000-0000-0000-000000000001",
        "title": "A complete master video",
        "topic": "Explain one evidence-led comparison with linked adaptations.",
        "platform": "all",
        "primary_platform": "facebook",
        "target_platforms": [],
        "format_name": "master_video",
        "duration_seconds": 150,
        "short_cut_count": 2,
        "scheduled_for": "2026-08-01",
    }
    value.update(overrides)
    return value


def test_all_platform_request_normalizes_master_and_derivatives() -> None:
    request = P110CreateContentRequest(**request_payload())
    assert request.primary_platform == "facebook"
    assert request.target_platforms == list(ALL_PLATFORMS)
    assert request.duration_seconds == 150
    assert request.short_cut_count == 2
    assert set(PLATFORM_PROFILES) == set(ALL_PLATFORMS)
    assert PLATFORM_PROFILES["facebook"]["aspect_ratio"] == "4:5"
    assert PLATFORM_PROFILES["youtube"]["aspect_ratio"] == "16:9"
    assert PLATFORM_PROFILES["tiktok"]["aspect_ratio"] == "9:16"


def test_duration_and_short_cut_boundaries_fail_closed() -> None:
    for duration in (9, 151):
        with pytest.raises(ValidationError):
            P110CreateContentRequest(**request_payload(duration_seconds=duration))
    with pytest.raises(ValidationError):
        P110CreateContentRequest(**request_payload(short_cut_count=3))
    with pytest.raises(ValidationError):
        P110CreateContentRequest(**request_payload(platform="unknown"))


def test_source_validation_rejects_private_and_credential_urls_without_network() -> None:
    for value in (
        "http://example.com/source",
        "https://localhost/source",
        "https://user:password@example.com/source",
        "https://service.internal/source",
    ):
        with pytest.raises(P110Error):
            _assert_public_https_url(value)


def test_automatic_evidence_matching_is_conservative() -> None:
    strong = AutomaticScriptEvidenceService._match_score(
        "African elephants communicate using low frequency rumbles",
        "Elephant communication includes low frequency rumbles used by African elephants",
    )
    weak = AutomaticScriptEvidenceService._match_score(
        "African elephants communicate using low frequency rumbles",
        "A page about unrelated marine biology and coral reefs",
    )
    assert strong >= 0.45
    assert weak < 0.45
    assert AutomaticScriptEvidenceService._numbers_are_preserved(
        "A call can travel 8 kilometres",
        "The call can travel 8 kilometres",
    )
    assert not AutomaticScriptEvidenceService._numbers_are_preserved(
        "A call can travel 8 kilometres",
        "The call can travel several kilometres",
    )


def test_four_brand_onboarding_retains_three_fixed_voice_contract() -> None:
    source = ONBOARDING.read_text(encoding="utf-8")
    for slug, label, url in (
        ("ani-films", "Ani Films", "https://www.facebook.com/people/Ani-Films/61563298430902/"),
        ("animal-x", "Animal X", "https://www.facebook.com/people/Animal-X/61566325046583/"),
        ("rawr-nation", "Rawr Nation TV", "https://www.facebook.com/RawrNationTV"),
        ("historiq", "Historiq", "https://www.facebook.com/people/Historiq/61580906280508/"),
    ):
        assert f'"slug": "{slug}"' in source
        assert f'"display_name": "{label}"' in source
        assert url in source
    assert "KOKORO_PRIMARY_VOICE" in source
    assert "KOKORO_ENERGETIC_VOICE" in source
    assert "KOKORO_SERIOUS_VOICE" in source
    assert '"is_default": True' in source
    assert source.count('"role": "primary"') == 1
    assert source.count('"role": "energetic"') == 1
    assert source.count('"role": "serious"') == 1
    assert "historical" not in source.lower() or "existing" in source.lower()


def test_schema_is_forward_only_and_records_explicit_overrides() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    family = FAMILY_MIGRATION.read_text(encoding="utf-8")
    override = OVERRIDE_MIGRATION.read_text(encoding="utf-8")
    for source in (migration, family, override):
        assert "DROP TABLE" not in source
        assert "TRUNCATE" not in source
        assert "DELETE FROM football_brief.script" not in source
    assert "brand_review_policies" in migration
    assert "script_source_research_runs" in migration
    assert "script_source_research_candidates" in migration
    assert "content_family_id" in migration
    assert "variant_type IN ('master','adaptation','short_cut')" in migration
    assert "target_duration_seconds BETWEEN 10 AND 150" in migration
    assert "self_review boolean NOT NULL DEFAULT false" in migration
    assert "Admin role is required for script self-review" in migration
    assert "initialize_content_family" in family
    assert "unsupported_claim_override boolean NOT NULL DEFAULT false" in override
    assert "Super Admin role is required for unsupported factual claim override" in override
    assert "matching_override_total" in override
    assert "unsupported_claim_snapshot" in override


def test_review_policies_are_seeded_after_operator_onboarding() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    onboarding = ONBOARDING_V2.read_text(encoding="utf-8")
    assert "Migrations never invent login or audit actors" in migration
    assert "INSERT INTO football_brief.brand_review_policies" not in migration
    assert "INSERT INTO football_brief.brand_review_policies" in onboarding
    assert "admin_self_review_allowed" in onboarding
    assert "independent_reviewer_available" in onboarding


def test_runtime_keeps_research_safe_and_super_admin_override_audited() -> None:
    source = RUNTIME.read_text(encoding="utf-8")
    patch = PATCH.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    assert "operator-controlled source research" in source
    assert "operator_triggered" in source
    assert "ipaddress.ip_address" in source
    assert "ip.is_private" in source
    assert "source_url_must_be_public_https" in source
    assert "source_url_validation_failed" in source
    assert "evidence_digest" in source
    assert "working_script_revision_required_for_sources" in source
    assert "self_review" in source
    assert "Same-session Admin progression" in source
    assert "actor.is_super_admin" in patch
    assert "unsupported_claim_snapshot" in patch
    assert "AutomaticScriptEvidenceService" in patch
    assert "automatic_approval\": False" in (ROOT / "src" / "application" / "scripts" / "automatic_evidence.py").read_text(encoding="utf-8")
    assert "install_p111_worker_evidence_patch" in worker


def test_creator_studio_exposes_complete_operator_path() -> None:
    api = API.read_text(encoding="utf-8")
    ui = UI.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    for token in (
        "/p110/content",
        "contentFamily",
        "researchClaim",
        "addManualSource",
        "attachSource",
        "reviewPolicy",
        "setReviewPolicy",
    ):
        assert token in api
    assert "All platforms" in ui
    assert "Custom duration (10–150 seconds)" in ui
    assert "2 cuts" in ui
    assert "Research web" in ui
    assert "Validate and attach" in ui
    assert "Same-session Admin review" in ui
    assert "Content family" in ui
    assert "studio-v2-p110.js" in index


def test_windows_upgrade_preserves_secrets_and_keeps_current_schema_head() -> None:
    deploy = DEPLOY.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    config_heads = [
        line.split("=", 1)[1]
        for line in config.splitlines()
        if line.startswith("OPS_MIGRATION_HEAD=")
    ]
    assert len(config_heads) == 1
    migration_head = config_heads[0]
    assert int(migration_head.split("_", 1)[0]) >= 95
    assert (ROOT / "migrations" / migration_head).is_file()
    assert f'$values["OPS_MIGRATION_HEAD"] = "{migration_head}"' in deploy
    assert "Sync-P110Environment" in deploy
    assert "OPERATOR_API_KEYS_JSON" not in deploy
    assert "KOKORO_PRIMARY_VOICE" in deploy
    assert "LOCAL_AUTO_RESEARCH_MINIMUM_MATCH" in deploy
    assert "P113_PILOT_TARGET_ATTEMPTS" in deploy
