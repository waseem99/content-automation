from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from pydantic import SecretStr

from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations
from src.infrastructure.database.settings import DatabaseSettings


ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.getenv("FOOTBALL_BRIEF_TEST_DATABASE_URL", "")
pytestmark = pytest.mark.integration


def test_duplicate_legacy_evidence_converges_on_one_canonical_asset(tmp_path: Path) -> None:
    if not TEST_DSN:
        pytest.skip("FOOTBALL_BRIEF_TEST_DATABASE_URL is not configured")

    staged = tmp_path / "migrations"
    staged.mkdir()
    for filename in (
        "0001_phase0_asset_rights.sql",
        "0002_phase1_workflow_foundation.sql",
    ):
        shutil.copy2(ROOT / "migrations" / filename, staged / filename)

    settings = DatabaseSettings(
        _env_file=None,
        url=SecretStr(TEST_DSN),
        migrations_dir=staged,
        require_schema=False,
        pool_min_size=1,
        pool_max_size=2,
    )
    database = Database(settings)
    database.open(require_schema=False)
    try:
        with database.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        apply_migrations(database, staged)

        with database.transaction() as conn:
            first = conn.execute(
                """
                INSERT INTO football_brief.assets (
                    asset_type, storage_uri, sha256
                ) VALUES ('image', 'workspace:///first.png', %s)
                RETURNING id
                """,
                ("1" * 64,),
            ).fetchone()["id"]
            second = conn.execute(
                """
                INSERT INTO football_brief.assets (
                    asset_type, storage_uri, sha256
                ) VALUES ('image', 'workspace:///second.png', %s)
                RETURNING id
                """,
                ("2" * 64,),
            ).fetchone()["id"]
            evidence_hash = "e" * 64
            conn.execute(
                """
                INSERT INTO football_brief.rights_evidence (
                    asset_id, evidence_type, storage_uri, sha256, uploaded_by
                ) VALUES
                    (%s, 'license', 'workspace:///license-a.pdf', %s, 'first'),
                    (%s, 'license', 'workspace:///license-b.pdf', %s, 'second')
                """,
                (first, evidence_hash, second, evidence_hash),
            )

        shutil.copy2(
            ROOT / "migrations" / "0003_canonical_rights_evidence.sql",
            staged / "0003_canonical_rights_evidence.sql",
        )
        apply_migrations(database, staged)

        with database.transaction() as conn:
            rows = conn.execute(
                """
                SELECT evidence_asset_id
                FROM football_brief.rights_evidence
                ORDER BY created_at
                """
            ).fetchall()
            canonical_count = conn.execute(
                "SELECT count(*) AS total FROM football_brief.assets WHERE sha256 = %s",
                (evidence_hash,),
            ).fetchone()["total"]

        assert len(rows) == 2
        assert rows[0]["evidence_asset_id"] == rows[1]["evidence_asset_id"]
        assert canonical_count == 1
    finally:
        with database.transaction() as conn:
            conn.execute("DROP SCHEMA IF EXISTS football_brief CASCADE")
        database.close()
