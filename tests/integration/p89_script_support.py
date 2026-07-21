from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr

from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")


@pytest.fixture()
def p89_database() -> Database:
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
def p89_seeded(p89_database: Database) -> dict[str, object]:
    operators = {
        "admin": ("admin.one", "Admin One", "admin"),
        "producer": ("producer.one", "Producer One", "producer"),
        "reviewer": ("reviewer.one", "Reviewer One", "reviewer"),
        "outsider": ("producer.outside", "Outside Producer", "producer"),
    }
    with p89_database.transaction() as conn:
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
               (slug, display_name, niche, primary_platform, content_mode, monthly_target)
               VALUES ('script-ocean','Script Ocean','Marine education','facebook','video',20)
               RETURNING id"""
        ).fetchone()
        brand_two = conn.execute(
            """INSERT INTO football_brief.brands
               (slug, display_name, niche, primary_platform, content_mode, monthly_target)
               VALUES ('script-space','Script Space','Space education','youtube_shorts','video',20)
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
               VALUES ('kokoro-onnx','af_heart','Script Voice','premade','approved',
                       ARRAY['en'], ARRAY['facebook','youtube_shorts'], 'admin.one', now())
               RETURNING id"""
        ).fetchone()

        profiles: dict[str, object] = {}
        for key, brand_id, platform in (
            ("one", brand_one["id"], "facebook"),
            ("two", brand_two["id"], "youtube_shorts"),
        ):
            profile = conn.execute(
                """INSERT INTO football_brief.brand_profiles
                   (brand_id, version, default_language, audience, tone,
                    content_restrictions, platforms, budget, created_by)
                   VALUES (%s,1,'en-US','{"age":"18-34"}'::jsonb,
                           'clear factual narration','{"avoid":["sensationalism"]}'::jsonb,
                           ARRAY[%s],'{"monthly_local_usd":0}'::jsonb,'admin.one')
                   RETURNING id""",
                (brand_id, platform),
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
            profiles[key] = profile["id"]

        plans: dict[str, object] = {}
        contents: dict[str, object] = {}
        workflows: dict[str, object] = {}
        for key, brand_id, profile_id, title, semantic in (
            (
                "one",
                brand_one["id"],
                profiles["one"],
                "How octopus arms sense the world",
                "octopus-sensing-script",
            ),
            (
                "two",
                brand_two["id"],
                profiles["two"],
                "How satellites stay in orbit",
                "satellite-orbit-script",
            ),
        ):
            plan = conn.execute(
                """INSERT INTO football_brief.monthly_content_plans
                   (brand_id, month_start, target_count, status, created_by)
                   VALUES (%s, DATE '2026-10-01', 20, 'draft', 'admin.one')
                   RETURNING id""",
                (brand_id,),
            ).fetchone()
            content = conn.execute(
                """INSERT INTO football_brief.portfolio_content
                   (plan_id, scheduled_for, title, concept, format,
                    concept_fingerprint, semantic_key, brand_profile_id)
                   VALUES (%s, DATE '2026-10-02', %s,
                           %s, 'vertical_short', %s, %s, %s)
                   RETURNING id, version""",
                (
                    plan["id"],
                    title,
                    f"Explain {title.lower()} with a factual mechanism and one practical takeaway.",
                    ("1" if key == "one" else "2") * 64,
                    semantic,
                    profile_id,
                ),
            ).fetchone()
            workflow_id = uuid4()
            workflow_version_id = uuid4()
            conn.execute(
                """INSERT INTO football_brief.production_workflows
                   (id, portfolio_content_id, current_stage, status, current_version_id,
                    lock_version, created_by)
                   VALUES (%s,%s,'script_draft','active',%s,1,'admin.one')""",
                (workflow_id, content["id"], workflow_version_id),
            )
            conn.execute(
                """INSERT INTO football_brief.production_workflow_versions
                   (id, workflow_id, version, basis_content_version, status, snapshot,
                    created_by, last_edited_by)
                   VALUES (%s,%s,1,%s,'working','{}'::jsonb,'admin.one','admin.one')""",
                (workflow_version_id, workflow_id, content["version"]),
            )
            plans[key] = plan["id"]
            contents[key] = content["id"]
            workflows[key] = workflow_id

    return {
        "brand_one": brand_one["id"],
        "brand_two": brand_two["id"],
        "profile_one": profiles["one"],
        "profile_two": profiles["two"],
        "plan_one": plans["one"],
        "plan_two": plans["two"],
        "content_one": contents["one"],
        "content_two": contents["two"],
        "workflow_one": workflows["one"],
        "workflow_two": workflows["two"],
        **{key: value[0] for key, value in operators.items()},
    }
