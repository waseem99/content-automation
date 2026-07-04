"""PostgreSQL integration tests for migration and repository contracts.

Set FOOTBALL_BRIEF_TEST_DATABASE_URL to a dedicated disposable test database.
The fixture drops and recreates the football_brief schema.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.domain.foundation import ContentItemCreate
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations, migration_status
from src.infrastructure.database.settings import DatabaseSettings
from src.infrastructure.database.uow import unit_of_work


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


def test_all_migrations_apply_and_health_is_ready(database: Database) -> None:
    health = database.health_check(ROOT / "migrations")
    assert health.ok is True
    assert health.schema_present is True
    assert health.migrations_table_present is True
    assert set(health.expected_migrations).issubset(health.applied_migrations)
    assert all(
        row.applied and row.checksum_matches
        for row in migration_status(database, ROOT / "migrations")
    )


def test_unit_of_work_commits_repository_records(database: Database) -> None:
    with unit_of_work(database) as uow:
        item = uow.content_items.create(
            ContentItemCreate(
                slug="foundation-smoke-test",
                working_title="Foundation smoke test",
                created_by="pytest",
            )
        )

    with unit_of_work(database) as uow:
        loaded = uow.content_items.get(item.id)
    assert loaded.slug == "foundation-smoke-test"


def test_unit_of_work_rolls_back_all_writes(database: Database) -> None:
    slug = "must-roll-back"
    with pytest.raises(RuntimeError, match="rollback"):
        with unit_of_work(database) as uow:
            uow.content_items.create(
                ContentItemCreate(slug=slug, working_title="Rollback", created_by="pytest")
            )
            raise RuntimeError("rollback")

    with unit_of_work(database) as uow:
        assert uow.content_items.get_by_slug(slug) is None


def test_repository_parameters_do_not_execute_injected_sql(database: Database) -> None:
    malicious_slug = "safe'; DROP SCHEMA football_brief CASCADE; --"
    with unit_of_work(database) as uow:
        item = uow.content_items.create(
            ContentItemCreate(
                slug=malicious_slug,
                working_title="Parameterized query test",
                created_by="pytest",
            )
        )
    assert item.slug == malicious_slug
    assert database.health_check(ROOT / "migrations").schema_present is True


def test_migration_checksum_matches_file_bytes(database: Database) -> None:
    for row in migration_status(database, ROOT / "migrations"):
        expected = hashlib.sha256(
            (ROOT / "migrations" / row.filename).read_bytes()
        ).hexdigest()
        assert row.checksum == expected
        assert row.checksum_matches is True
