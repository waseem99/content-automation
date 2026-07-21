from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.application.renderers.models import RendererEntryRequest, RendererOperation
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")


@pytest.fixture()
def p93_database() -> Database:
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
def p93_seeded(p93_database: Database) -> dict[str, object]:
    operators = {
        "admin": ("admin.renderer", "Renderer Admin", "admin"),
        "producer": ("producer.renderer", "Renderer Producer", "producer"),
        "reviewer": ("reviewer.renderer", "Renderer Reviewer", "reviewer"),
        "outsider": ("producer.other", "Other Producer", "producer"),
    }
    with p93_database.transaction() as conn:
        user_ids = {}
        for key, (operator_id, display_name, role) in operators.items():
            user = conn.execute(
                """INSERT INTO football_brief.operator_users
                   (operator_id,display_name,created_by)
                   VALUES (%s,%s,'bootstrap') RETURNING id""",
                (operator_id, display_name),
            ).fetchone()
            conn.execute(
                """INSERT INTO football_brief.operator_user_roles
                   (operator_user_id,role,assigned_by)
                   VALUES (%s,%s,'bootstrap')""",
                (user["id"], role),
            )
            user_ids[key] = user["id"]

        brand_one = conn.execute(
            """INSERT INTO football_brief.brands
               (slug,display_name,niche,primary_platform,content_mode,monthly_target)
               VALUES ('renderer-one','Renderer One','Education','facebook','video',20)
               RETURNING id"""
        ).fetchone()
        brand_two = conn.execute(
            """INSERT INTO football_brief.brands
               (slug,display_name,niche,primary_platform,content_mode,monthly_target)
               VALUES ('renderer-two','Renderer Two','Education','youtube_shorts','video',20)
               RETURNING id"""
        ).fetchone()
        for key in ("producer", "reviewer"):
            conn.execute(
                """INSERT INTO football_brief.operator_brand_assignments
                   (operator_user_id,brand_id,assigned_by)
                   VALUES (%s,%s,'admin.renderer')""",
                (user_ids[key], brand_one["id"]),
            )
        conn.execute(
            """INSERT INTO football_brief.operator_brand_assignments
               (operator_user_id,brand_id,assigned_by)
               VALUES (%s,%s,'admin.renderer')""",
            (user_ids["outsider"], brand_two["id"]),
        )

        plan_one = conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id,month_start,target_count,status,created_by)
               VALUES (%s,DATE '2026-11-01',20,'draft','admin.renderer') RETURNING id""",
            (brand_one["id"],),
        ).fetchone()
        content_one = conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id,scheduled_for,title,concept,format,concept_fingerprint,semantic_key)
               VALUES (%s,DATE '2026-11-02','Renderer test','Test renderer routing.',
                       'vertical_short',%s,'renderer-test-one') RETURNING id,version""",
            (plan_one["id"], "a" * 64),
        ).fetchone()
        plan_two = conn.execute(
            """INSERT INTO football_brief.monthly_content_plans
               (brand_id,month_start,target_count,status,created_by)
               VALUES (%s,DATE '2026-11-01',20,'draft','admin.renderer') RETURNING id""",
            (brand_two["id"],),
        ).fetchone()
        content_two = conn.execute(
            """INSERT INTO football_brief.portfolio_content
               (plan_id,scheduled_for,title,concept,format,concept_fingerprint,semantic_key)
               VALUES (%s,DATE '2026-11-03','Other renderer test','Other brand.',
                       'vertical_short',%s,'renderer-test-two') RETURNING id,version""",
            (plan_two["id"], "b" * 64),
        ).fetchone()

    return {
        "brand_one": brand_one["id"],
        "brand_two": brand_two["id"],
        "content_one": content_one["id"],
        "content_one_version": content_one["version"],
        "content_two": content_two["id"],
        "content_two_version": content_two["version"],
        **{key: value[0] for key, value in operators.items()},
    }


def simulated_entry_request(*, parent_entry_id=None, base_usd: str = "0") -> RendererEntryRequest:
    return RendererEntryRequest(
        provider_key="simulated",
        provider_display_name="CI Simulated Renderer",
        model_key="sim-video-v1",
        model_display_name="Simulated Video v1",
        operation=RendererOperation.IMAGE_TO_VIDEO,
        adapter_kind="simulated",
        supported_formats=("vertical_9_16", "square_1_1"),
        min_duration_seconds=Decimal("2"),
        max_duration_seconds=Decimal("10"),
        duration_step_seconds=Decimal("1"),
        supported_resolutions=(
            {"width": 704, "height": 1280},
            {"width": 1080, "height": 1920},
        ),
        capabilities={
            "camera_control": True,
            "character_consistency": True,
            "negative_prompt": True,
        },
        expected_latency_seconds={"p50": 15, "p95": 30, "per_output_second": 2},
        pricing={"base_usd": base_usd, "per_second_usd": "0", "per_megapixel_second_usd": "0"},
        pricing_currency="USD",
        quality_rating=Decimal("80"),
        commercial_use_allowed=True,
        usage_terms_url="https://example.test/simulated-terms",
        usage_evidence_digest="d" * 64,
        usage_evidence_recorded_at=datetime.now(timezone.utc),
        data_handling={"retention_days": 0, "training_use": False},
        notes="CI-only zero-fee simulated renderer.",
        parent_entry_id=parent_entry_id,
    )
