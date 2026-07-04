from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.infrastructure.database.migrations import (
    MigrationError,
    _strip_outer_transaction,
    discover_migrations,
)


def test_discover_migrations_is_ordered_and_checksummed(tmp_path: Path) -> None:
    second = tmp_path / "0002_second.sql"
    first = tmp_path / "0001_first.sql"
    second.write_text("BEGIN; SELECT 2; COMMIT;", encoding="utf-8")
    first.write_text("BEGIN; SELECT 1; COMMIT;", encoding="utf-8")

    migrations = discover_migrations(tmp_path)

    assert [migration.filename for migration in migrations] == [
        "0001_first.sql",
        "0002_second.sql",
    ]
    assert migrations[0].checksum == hashlib.sha256(first.read_bytes()).hexdigest()


def test_discover_migrations_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(MigrationError, match="No numbered SQL migrations"):
        discover_migrations(tmp_path)


def test_strip_outer_transaction_preserves_function_body() -> None:
    sql = """
    BEGIN;
    CREATE FUNCTION example() RETURNS void LANGUAGE plpgsql AS $$
    BEGIN
      PERFORM 1;
    END;
    $$;
    COMMIT;
    """
    body = _strip_outer_transaction(sql)
    assert "CREATE FUNCTION" in body
    assert "PERFORM 1" in body
    assert not body.lstrip().upper().startswith("BEGIN;")
    assert not body.rstrip().upper().endswith("COMMIT;")


def test_strip_outer_transaction_rejects_unbalanced_wrapper() -> None:
    with pytest.raises(MigrationError, match="both outer BEGIN and COMMIT"):
        _strip_outer_transaction("BEGIN; SELECT 1;")
