from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")


@pytest.fixture()
def p88_database() -> Database:
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")
    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=ROOT / "migrations",
        require_schema=False,
        pool_min_size=1,
        pool_max_size=5,
    )
    database = Database(settings)
    database.open(require_schema=False)
    with database.transaction() as conn:
        conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
    apply_migrations(database, settings.migrations_dir)
    try:
        yield database
    finally:
        with database.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        database.close()


@pytest.fixture()
def p88_seeded(p88_database: Database) -> dict[str, object]:
    operators = {
        "admin": ("admin.one", "Admin One", "admin"),
        "producer": ("producer.one", "Producer One", "producer"),
        "reviewer": ("reviewer.one", "Reviewer One", "reviewer"),
        "outsider": ("producer.outside", "Outside Producer", "producer"),
    }
    with p88_database.transaction() as conn:
        operator_rows: dict[str, object] = {}
        for key, (operator_id, display_name, role) in operators.items():
            user = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id, display_name, created_by)
                   VALUES (%s,%s,'bootstrap') RETURNING id""",
                (operator_id, display_name),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.operator_user_roles
                   (operator_user_id, role, assigned_by)
                   VALUES (%s,%s,'bootstrap')""",
                (user["id"], role),
            )
            operator_rows[key] = user["id"]

        brand_one = conn.execute(
            """INSERT INTO football_brief.brands
               (slug, display_name, niche, primary_platform, content_mode,
                monthly_target, content_pillars)
               VALUES ('ocean-facts','Ocean Facts','Marine education','facebook','video',40,
                       '["education","conservation","myth"]'::jsonb)
               RETURNING id"""
        ).fetchone()
        brand_two = conn.execute(
            """INSERT INTO football_brief.brands
               (slug, display_name, niche, primary_platform, content_mode,
                monthly_target, content_pillars)
               VALUES ('space-facts','Space Facts','Space education','youtube_shorts','video',20,
                       '["education","missions"]'::jsonb)
               RETURNING id"""
        ).fetchone()

        for key in ("producer", "reviewer"):
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id, brand_id, assigned_by)
                   VALUES (%s,%s,'admin.one')""",
                (operator_rows[key], brand_one["id"]),
            )
        conn.execute(
            """INSERT INTO football_brief.operator_brand_assignments
               (operator_user_id, brand_id, assigned_by)
               VALUES (%s,%s,'admin.one')""",
            (operator_rows["outsider"], brand_two["id"]),
        )

        voice = conn.execute(
            """INSERT INTO football_brief.approved_voices
               (provider, provider_voice_id, display_name, voice_type, approval_status,
                allowed_languages, allowed_platforms, approved_by, approved_at)
               VALUES ('kokoro-onnx','af_heart','Concept Voice','premade','approved',
                       ARRAY['en'], ARRAY['facebook','youtube_shorts'], 'admin.one', now())
               RETURNING id"""
        ).fetchone()

        profiles: dict[str, object] = {}
        for brand_key, brand_id, platforms in (
            ("brand_one", brand_one["id"], ["facebook"]),
            ("brand_two", brand_two["id"], ["youtube_shorts"]),
        ):
            profile = conn.execute(
                """INSERT INTO football_brief.brand_profiles
                   (brand_id, version, default_language, audience, tone, visual_rules,
                    content_restrictions, cadence, platforms, budget, created_by)
                   VALUES (%s,1,'en-US',
                           '{"age":"18-34","monetization_goal":"sponsorship"}'::jsonb,
                           'clear factual narration',
                           '{"pace":"fast"}'::jsonb,
                           '{"avoid":["graphic injury"]}'::jsonb,
                           '{"weekly":6}'::jsonb,
                           %s,'{"monthly_local_usd":0}'::jsonb,'admin.one')
                   RETURNING id""",
                (brand_id, platforms),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.brand_narration_presets
                   (brand_profile_id, preset_key, display_name, role, approved_voice_id,
                    language, is_default)
                   VALUES (%s,'primary','Primary','primary',%s,'en-US',true)""",
                (profile["id"], voice["id"]),
            )
            conn.execute(
                """UPDATE football_brief.brand_profiles
                   SET status='active', activated_by='admin.one', activated_at=now()
                   WHERE id=%s""",
                (profile["id"],),
            )
            profiles[brand_key] = profile["id"]

        plan_one = conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id, month_start, target_count, status, created_by)
               VALUES (%s, DATE '2026-09-01', 40, 'draft', 'admin.one')
               RETURNING id""",
            (brand_one["id"],),
        ).fetchone()
        plan_two = conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id, month_start, target_count, status, created_by)
               VALUES (%s, DATE '2026-09-01', 20, 'draft', 'admin.one')
               RETURNING id""",
            (brand_two["id"],),
        ).fetchone()

    return {
        "brand_one": brand_one["id"],
        "brand_two": brand_two["id"],
        "profile_one": profiles["brand_one"],
        "profile_two": profiles["brand_two"],
        "plan_one": plan_one["id"],
        "plan_two": plan_two["id"],
        **{key: value[0] for key, value in operators.items()},
    }
