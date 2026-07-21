from pathlib import Path

import pytest

from src.application.brand_profile_service import (
    language_matches,
    select_narration_preset,
    validate_narration_presets,
    validate_profile_payload,
)


ROOT = Path(__file__).resolve().parents[2]


def profile_payload() -> dict:
    return {
        "default_language": "en-US",
        "audience": {"age": "18-34"},
        "tone": "warm, factual, cinematic",
        "visual_rules": {"palette": "earth and ocean"},
        "content_restrictions": {"avoid": ["graphic injury"]},
        "cadence": {"weekly": 6},
        "platforms": ["facebook", "youtube_shorts"],
        "budget": {"monthly_local_usd": 0, "monthly_managed_usd": 100},
    }


def preset(key: str, role: str, *, default: bool = False, formats=None, topics=None) -> dict:
    return {
        "preset_key": key,
        "display_name": key.replace("_", " ").title(),
        "role": role,
        "approved_voice_id": "11111111-1111-1111-1111-111111111111",
        "language": "en-US",
        "speed": 1.0,
        "format_filters": formats or [],
        "topic_filters": topics or [],
        "is_default": default,
    }


def test_profile_requires_tone_platform_and_nonnegative_budget() -> None:
    validate_profile_payload(profile_payload())
    invalid = profile_payload()
    invalid["budget"] = {"monthly_managed_usd": -1}
    with pytest.raises(ValueError, match="cannot be negative"):
        validate_profile_payload(invalid)
    invalid = profile_payload()
    invalid["platforms"] = []
    with pytest.raises(ValueError, match="target platform"):
        validate_profile_payload(invalid)


def test_profile_requires_one_to_three_unique_presets_and_one_default() -> None:
    valid = [preset("primary", "primary", default=True), preset("fast", "energetic")]
    validate_narration_presets(valid)
    with pytest.raises(ValueError, match="one to three"):
        validate_narration_presets([])
    with pytest.raises(ValueError, match="exactly one"):
        validate_narration_presets([preset("primary", "primary")])
    with pytest.raises(ValueError, match="roles must be unique"):
        validate_narration_presets(
            [preset("one", "primary", default=True), preset("two", "primary")]
        )
    with pytest.raises(ValueError, match="one to three"):
        validate_narration_presets(
            [
                preset("one", "primary", default=True),
                preset("two", "energetic"),
                preset("three", "serious"),
                preset("four", "primary"),
            ]
        )


def test_language_matching_accepts_base_language_for_regional_request() -> None:
    assert language_matches(["en"], "en-US")
    assert language_matches(["ur-PK"], "ur-PK")
    assert not language_matches(["en"], "ur-PK")


def test_selection_prefers_matching_format_and_topic_then_default_fallback() -> None:
    rows = [
        {**preset("primary", "primary", default=True), "id": "p1", "active": True},
        {
            **preset("fast", "energetic", formats=["vertical_short"], topics=["myth"]),
            "id": "p2",
            "active": True,
        },
        {**preset("serious", "serious", topics=["conservation"]), "id": "p3", "active": True},
    ]
    selected = select_narration_preset(
        rows, language="en-US", format_name="vertical_short", topic_type="myth"
    )
    assert selected["id"] == "p2"
    fallback = select_narration_preset(
        rows, language="en-US", format_name="vertical_feature", topic_type="general"
    )
    assert fallback["id"] == "p1"
    with pytest.raises(ValueError, match="no eligible"):
        select_narration_preset(rows, language="ur-PK", format_name="vertical_short")


def test_migration_pins_profile_and_preset_history_and_reuses_voice_registry() -> None:
    migration = (ROOT / "migrations" / "0030_brand_profiles_and_narration_presets.sql").read_text(encoding="utf-8")
    service = (ROOT / "src" / "application" / "brand_profile_service.py").read_text(encoding="utf-8")
    runtime = (ROOT / "src" / "operator_api" / "brand_profiles_runtime.py").read_text(encoding="utf-8")
    client = (ROOT / "web" / "static-creator-ui" / "assets" / "portfolio-api.js").read_text(encoding="utf-8")
    admin = (ROOT / "web" / "static-creator-ui" / "assets" / "brand-profile-admin.js").read_text(encoding="utf-8")
    styles = (ROOT / "web" / "static-creator-ui" / "assets" / "brand-profile-admin.css").read_text(encoding="utf-8")

    assert migration.startswith("-- Football Brief")
    assert "CREATE TABLE football_brief.brand_profiles" in migration
    assert "CREATE TABLE football_brief.brand_narration_presets" in migration
    assert "REFERENCES football_brief.approved_voices" in migration
    assert "at most three active narration presets" in migration
    assert "ADD COLUMN brand_profile_id" in migration
    assert "ADD COLUMN narration_preset_id" in migration
    assert migration.rstrip().endswith("COMMIT;")
    assert "narration_selection_already_pinned" in service
    assert "/portfolio/brands/{brand_id}/profiles" in runtime
    assert "/portfolio/approved-voices" in runtime
    assert "activateBrandProfile" in client
    assert "pinNarrationSelection" in client
    assert '["brand-profile-admin", "brand-profile-admin.css", "brand-profile-admin.js"]' in client
    assert "void import(new URL(js, scriptBase).href)" in client
    assert "brand-profile-settings" in admin
    assert "document.readyState" in admin
    assert ".brand-profile-dialog" in styles
