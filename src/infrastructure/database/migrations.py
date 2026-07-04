"""Forward-only PostgreSQL migration discovery and execution."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from psycopg import Connection

from src.infrastructure.database.connection import Database


class MigrationError(RuntimeError):
    """Base class for migration failures."""


class MigrationChecksumError(MigrationError):
    """Raised when an applied migration file has been modified."""


@dataclass(frozen=True, slots=True)
class Migration:
    filename: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True, slots=True)
class MigrationStatus:
    filename: str
    checksum: str
    applied: bool
    checksum_matches: bool | None


_OUTER_BEGIN = re.compile(r"^\s*BEGIN\s*;", re.IGNORECASE)
_OUTER_COMMIT = re.compile(r"COMMIT\s*;\s*$", re.IGNORECASE)


def _canonical_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _strip_outer_transaction(sql: str) -> str:
    """Remove one explicit outer BEGIN/COMMIT pair.

    Foundation migrations carry their own transaction markers so they can also
    be applied manually with psql. The runner removes only that outer pair and
    executes the body together with the migration-history insert in one driver
    transaction.
    """

    without_begin, begin_count = _OUTER_BEGIN.subn("", sql, count=1)
    without_commit, commit_count = _OUTER_COMMIT.subn("", without_begin, count=1)
    if begin_count != commit_count:
        raise MigrationError("Migration must contain both outer BEGIN and COMMIT, or neither")
    return without_commit.strip()


def discover_migrations(directory: Path) -> list[Migration]:
    if not directory.exists():
        raise MigrationError(f"Migration directory does not exist: {directory}")

    paths = sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    if not paths:
        raise MigrationError(f"No numbered SQL migrations found in {directory}")

    migrations: list[Migration] = []
    seen: set[str] = set()
    for path in paths:
        if path.name in seen:
            raise MigrationError(f"Duplicate migration filename: {path.name}")
        seen.add(path.name)
        raw = _canonical_bytes(path)
        migrations.append(
            Migration(
                filename=path.name,
                path=path,
                checksum=hashlib.sha256(raw).hexdigest(),
                sql=raw.decode("utf-8"),
            )
        )
    return migrations


def _bootstrap_history(conn: Connection[dict]) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS football_brief")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS football_brief.schema_migrations (
            filename text PRIMARY KEY,
            checksum char(64) NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now(),
            applied_by text NOT NULL DEFAULT current_user
        )
        """
    )


def _applied(conn: Connection[dict]) -> dict[str, str]:
    rows = conn.execute(
        "SELECT filename, checksum FROM football_brief.schema_migrations ORDER BY filename"
    ).fetchall()
    return {row["filename"]: row["checksum"] for row in rows}


def migration_status(database: Database, directory: Path) -> list[MigrationStatus]:
    migrations = discover_migrations(directory)
    with database.transaction() as conn:
        _bootstrap_history(conn)
        applied = _applied(conn)

    return [
        MigrationStatus(
            filename=migration.filename,
            checksum=migration.checksum,
            applied=migration.filename in applied,
            checksum_matches=(
                applied[migration.filename] == migration.checksum
                if migration.filename in applied
                else None
            ),
        )
        for migration in migrations
    ]


def apply_migrations(database: Database, directory: Path) -> list[str]:
    migrations = discover_migrations(directory)
    applied_now: list[str] = []

    with database.transaction() as conn:
        _bootstrap_history(conn)

    for migration in migrations:
        with database.transaction() as conn:
            existing = conn.execute(
                "SELECT checksum FROM football_brief.schema_migrations WHERE filename = %s",
                (migration.filename,),
            ).fetchone()
            if existing:
                if existing["checksum"] != migration.checksum:
                    raise MigrationChecksumError(
                        f"Applied migration was modified: {migration.filename}"
                    )
                continue

            body = _strip_outer_transaction(migration.sql)
            if body:
                conn.execute(body)
            conn.execute(
                "INSERT INTO football_brief.schema_migrations (filename, checksum) "
                "VALUES (%s, %s)",
                (migration.filename, migration.checksum),
            )
            applied_now.append(migration.filename)

    return applied_now
