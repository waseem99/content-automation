from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr

from src.application.brand_profile_service import BrandProfileService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration


@pytest.fixture()
def database() -> Database:
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=False,
        pool_min_size=1,
        pool_max_size=2,
    )
    db = Database(settings)
    db.open(require_schema=False)
    with db.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    apply_migrations(db, settings.migrations_dir)
    try:
        yield db
    finally:
        with db.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        db.close()


@pytest.fixture()
def seeded(database: Database) -> dict[str, UUID]:
    with database.transaction() as conn:
        brand = conn.execute(
            """INSERT INTO football_brief.brands
               (slug, display_name, niche, primary_platform, content_mode, monthly_target)
               VALUES ('animal-x-test','Animal X Test','Animal behaviour','facebook','video',24)
               RETURNING id"""
        ).fetchone()
        primary = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider, provider_voice_id, display_name, voice_type, approval_status,
                allowed_languages, allowed_platforms, approved_by, approved_at)
               VALUES ('kokoro-onnx','af_heart','Animal X Primary','premade','approved',
                       ARRAY['en'], ARRAY['facebook'], 'admin.one', now())
               RETURNING id"""
        ).fetchone()
        energetic = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider, provider_voice_id, display_name, voice_type, approval_status,
                allowed_languages, allowed_platforms, approved_by, approved_at)
               VALUES ('kokoro-onnx','af_sky','Animal X Energetic','premade','approved',
                       ARRAY['en'], ARRAY['facebook'], 'admin.one', now())
               RETURNING id"""
        ).fetchone()
        pending = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider, provider_voice_id, display_name, voice_type, approval_status,
                allowed_languages, allowed_platforms)
               VALUES ('kokoro-onnx','af_pending','Pending Voice','premade','pending',
                       ARRAY['en'], ARRAY['facebook'])
               RETURNING id"""
        ).fetchone()
        plan = conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id, month_start, target_count, created_by)
               VALUES (%s, DATE '2026-08-01', 24, 'admin.one') RETURNING id""",
            (brand["id"],),
        ).fetchone()
        content = conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id, scheduled_for, title, concept, format, concept_fingerprint, semantic_key)
               VALUES (%s, DATE '2026-08-02', 'Octopus signals', 'Explain octopus arm sensing.',
                       'vertical_short', %s, 'octopus-arm-sensing') RETURNING id""",
            (plan["id"], "a" * 64),
        ).fetchone()
    return {
        "brand": brand["id"],
        "primary": primary["id"],
        "energetic": energetic["id"],
        "pending": pending["id"],
        "content": content["id"],
    }


def profile_payload(tone: str = "warm factual documentary") -> dict:
    return {
        "default_language": "en-US",
        "audience": {"age": "18-34", "interest": "animal behaviour"},
        "tone": tone,
        "visual_rules": {"palette": ["earth", "ocean"]},
        "content_restrictions": {"avoid": ["graphic injury"]},
        "cadence": {"weekly_short": 5, "weekly_feature": 1},
        "platforms": ["facebook"],
        "budget": {"monthly_local_usd": 0, "monthly_managed_usd": 100},
    }


def presets(primary: UUID, energetic: UUID) -> list[dict]:
    return [
        {
            "preset_key": "primary",
            "display_name": "Primary Documentary",
            "role": "primary",
            "approved_voice_id": primary,
            "language": "en-US",
            "speed": 0.98,
            "style": {"delivery": "warm and restrained"},
            "pronunciation_rules": {"cephalopod": "SEF-uh-lo-pod"},
            "format_filters": [],
            "topic_filters": [],
            "is_default": True,
        },
        {
            "preset_key": "energetic_short",
            "display_name": "Energetic Short",
            "role": "energetic",
            "approved_voice_id": energetic,
            "language": "en-US",
            "speed": 1.08,
            "style": {"delivery": "curious and fast"},
            "pronunciation_rules": {},
            "format_filters": ["vertical_short"],
            "topic_filters": ["myth"],
            "is_default": False,
        },
    ]


def test_profile_activation_selection_and_content_history_are_stable(database: Database, seeded: dict[str, UUID]) -> None:
    service = BrandProfileService(database)
    draft = service.create_draft(
        brand_id=seeded["brand"],
        profile=profile_payload(),
        presets=presets(seeded["primary"], seeded["energetic"]),
        actor="admin.one",
    )
    assert draft["ok"] is True
    assert draft["profile"]["version"] == 1
    assert draft["profile"]["status"] == "draft"

    activated = service.activate(
        brand_id=seeded["brand"],
        profile_id=draft["profile"]["id"],
        actor="admin.one",
    )
    assert activated["ok"] is True
    assert activated["profile"]["status"] == "active"

    selection = service.select(
        brand_id=seeded["brand"],
        language="en-US",
        format_name="vertical_short",
        topic_type="myth",
    )
    assert selection.preset_key == "energetic_short"
    assert selection.provider == "kokoro-onnx"
    assert selection.profile_version == 1

    pinned = service.bind_content(
        content_id=seeded["content"],
        preset_id=UUID(selection.preset_id),
    )
    assert pinned["ok"] is True
    assert str(pinned["item"]["brand_profile_id"]) == selection.profile_id
    assert str(pinned["item"]["narration_preset_id"]) == selection.preset_id

    second = service.create_draft(
        brand_id=seeded["brand"],
        profile=profile_payload("measured serious documentary"),
        presets=[
            {
                "preset_key": "serious",
                "display_name": "Serious Documentary",
                "role": "serious",
                "approved_voice_id": seeded["primary"],
                "language": "en-US",
                "speed": 0.92,
                "style": {"delivery": "measured"},
                "pronunciation_rules": {},
                "format_filters": [],
                "topic_filters": [],
                "is_default": True,
            }
        ],
        actor="admin.one",
    )
    service.activate(
        brand_id=seeded["brand"],
        profile_id=second["profile"]["id"],
        actor="admin.one",
    )

    with database.connection() as conn:
        old_profile = conn.execute(
            "SELECT status FROM football_brief.brand_profiles WHERE id=%s",
            (draft["profile"]["id"],),
        ).fetchone()
        content = conn.execute(
            "SELECT brand_profile_id, narration_preset_id FROM football_brief.portfolio_content WHERE id=%s",
            (seeded["content"],),
        ).fetchone()
    assert old_profile["status"] == "retired"
    assert str(content["brand_profile_id"]) == selection.profile_id
    assert str(content["narration_preset_id"]) == selection.preset_id

    replacement = service.select(brand_id=seeded["brand"], language="en-US")
    assert replacement.profile_version == 2
    assert replacement.preset_key == "serious"

    rebinding = service.bind_content(
        content_id=seeded["content"],
        preset_id=UUID(replacement.preset_id),
    )
    assert rebinding == {"ok": False, "error": "narration_selection_already_pinned"}


def test_unapproved_voice_cannot_enter_a_brand_profile(database: Database, seeded: dict[str, UUID]) -> None:
    service = BrandProfileService(database)
    with pytest.raises(ValueError, match="currently approved voice"):
        service.create_draft(
            brand_id=seeded["brand"],
            profile=profile_payload(),
            presets=[
                {
                    "preset_key": "pending",
                    "display_name": "Pending",
                    "role": "primary",
                    "approved_voice_id": seeded["pending"],
                    "language": "en-US",
                    "speed": 1.0,
                    "is_default": True,
                }
            ],
            actor="admin.one",
        )
