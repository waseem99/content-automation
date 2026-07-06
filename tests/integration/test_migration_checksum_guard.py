from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.infrastructure.database.migrations import MigrationChecksumError, apply_migrations
from tests.integration.rights_support import close_database, database_fixture


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "migrations"


@pytest.mark.integration
def test_applied_migration_checksum_rejects_changed_sql(tmp_path: Path) -> None:
    database = database_fixture()
    try:
        copied = tmp_path / "migrations"
        shutil.copytree(MIGRATIONS_DIR, copied)
        target = copied / "0001_phase0_asset_rights.sql"
        target.write_text(target.read_text(encoding="utf-8") + "\n-- changed after apply\n", encoding="utf-8")

        with pytest.raises(MigrationChecksumError, match="Applied migration was modified"):
            apply_migrations(database, copied)
    finally:
        close_database(database)
