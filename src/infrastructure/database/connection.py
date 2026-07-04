"""PostgreSQL connection pool, transactions, and readiness checks."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from src.infrastructure.database.settings import DatabaseSettings


class DatabaseUnavailableError(RuntimeError):
    """Raised when PostgreSQL cannot be reached or initialized."""


class DatabaseSchemaError(RuntimeError):
    """Raised when the expected platform schema has not been applied."""


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    ok: bool
    database_reachable: bool
    schema_present: bool
    migrations_table_present: bool
    applied_migrations: tuple[str, ...]
    expected_migrations: tuple[str, ...]
    error: str | None = None


class Database:
    """Owns the psycopg connection pool and transaction boundaries."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings
        self._pool = ConnectionPool(
            conninfo=settings.require_dsn(),
            min_size=settings.pool_min_size,
            max_size=settings.pool_max_size,
            timeout=settings.pool_timeout_sec,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": settings.connect_timeout_sec,
                "application_name": settings.application_name,
                "options": f"-c statement_timeout={settings.statement_timeout_ms}",
            },
            open=False,
            name="football-brief-db",
        )

    @property
    def is_open(self) -> bool:
        return not self._pool.closed

    def open(self, *, require_schema: bool | None = None) -> None:
        try:
            self._pool.open(wait=True, timeout=self.settings.pool_timeout_sec)
        except Exception as exc:
            raise DatabaseUnavailableError(f"Unable to open PostgreSQL pool: {exc}") from exc

        should_require_schema = (
            self.settings.require_schema if require_schema is None else require_schema
        )
        if should_require_schema:
            health = self.health_check()
            if not health.database_reachable:
                self.close()
                raise DatabaseUnavailableError(health.error or "PostgreSQL is unavailable")
            if not health.schema_present or not health.migrations_table_present:
                self.close()
                raise DatabaseSchemaError(
                    "Football Brief schema is not ready; run the migration command first"
                )

    def close(self) -> None:
        if not self._pool.closed:
            self._pool.close()

    def __enter__(self) -> "Database":
        self.open()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @contextmanager
    def connection(self) -> Iterator[Connection[dict]]:
        if self._pool.closed:
            raise DatabaseUnavailableError("Database pool is not open")
        with self._pool.connection(timeout=self.settings.pool_timeout_sec) as conn:
            yield conn

    @contextmanager
    def transaction(self) -> Iterator[Connection[dict]]:
        with self.connection() as conn:
            with conn.transaction():
                yield conn

    def health_check(self, migrations_dir: Path | None = None) -> DatabaseHealth:
        expected = tuple(
            path.name
            for path in sorted((migrations_dir or self.settings.migrations_dir).glob("*.sql"))
        )
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1").fetchone()
                schema_present = bool(
                    conn.execute(
                        "SELECT to_regnamespace('football_brief') IS NOT NULL AS present"
                    ).fetchone()["present"]
                )
                migrations_table_present = bool(
                    conn.execute(
                        "SELECT to_regclass('football_brief.schema_migrations') "
                        "IS NOT NULL AS present"
                    ).fetchone()["present"]
                )
                applied: tuple[str, ...] = ()
                if migrations_table_present:
                    rows = conn.execute(
                        "SELECT filename FROM football_brief.schema_migrations "
                        "ORDER BY filename"
                    ).fetchall()
                    applied = tuple(row["filename"] for row in rows)

            schema_ready = schema_present and migrations_table_present
            migrations_ready = not expected or set(expected).issubset(applied)
            return DatabaseHealth(
                ok=schema_ready and migrations_ready,
                database_reachable=True,
                schema_present=schema_present,
                migrations_table_present=migrations_table_present,
                applied_migrations=applied,
                expected_migrations=expected,
            )
        except Exception as exc:
            return DatabaseHealth(
                ok=False,
                database_reachable=False,
                schema_present=False,
                migrations_table_present=False,
                applied_migrations=(),
                expected_migrations=expected,
                error=str(exc),
            )
