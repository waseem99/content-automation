"""Operational CLI for database migrations and readiness checks.

Usage:
    python -m src.infrastructure.database.cli migrate
    python -m src.infrastructure.database.cli status
    python -m src.infrastructure.database.cli health
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations, migration_status
from src.infrastructure.database.settings import DatabaseSettings, get_database_settings


app = typer.Typer(help="Football Brief PostgreSQL foundation commands.")


def _database(*, require_schema: bool) -> tuple[DatabaseSettings, Database]:
    settings = get_database_settings()
    database = Database(settings)
    database.open(require_schema=require_schema)
    return settings, database


@app.command("migrate")
def migrate(
    migrations_dir: Path | None = typer.Option(
        None, "--migrations-dir", help="Override the configured migration directory"
    ),
) -> None:
    """Apply all pending forward-only migrations."""

    settings, database = _database(require_schema=False)
    directory = migrations_dir or settings.migrations_dir
    try:
        applied = apply_migrations(database, directory)
        if applied:
            typer.echo("Applied migrations:")
            for filename in applied:
                typer.echo(f"  - {filename}")
        else:
            typer.echo("Database is already up to date.")
    finally:
        database.close()


@app.command("status")
def status(
    migrations_dir: Path | None = typer.Option(
        None, "--migrations-dir", help="Override the configured migration directory"
    ),
) -> None:
    """Show migration application and checksum status."""

    settings, database = _database(require_schema=False)
    directory = migrations_dir or settings.migrations_dir
    try:
        rows = migration_status(database, directory)
        failed = False
        for row in rows:
            if not row.applied:
                label = "PENDING"
            elif row.checksum_matches:
                label = "APPLIED"
            else:
                label = "CHECKSUM_MISMATCH"
                failed = True
            typer.echo(f"{label:18} {row.filename}")
        if failed:
            raise typer.Exit(code=2)
    finally:
        database.close()


@app.command("health")
def health(
    migrations_dir: Path | None = typer.Option(
        None, "--migrations-dir", help="Override the configured migration directory"
    ),
    output_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Check database connectivity, schema presence, and migration readiness."""

    settings, database = _database(require_schema=False)
    directory = migrations_dir or settings.migrations_dir
    try:
        result = database.health_check(directory)
        payload = {
            "ok": result.ok,
            "database_reachable": result.database_reachable,
            "schema_present": result.schema_present,
            "migrations_table_present": result.migrations_table_present,
            "applied_migrations": list(result.applied_migrations),
            "expected_migrations": list(result.expected_migrations),
            "error": result.error,
        }
        if output_json:
            typer.echo(json.dumps(payload, indent=2))
        else:
            typer.echo(f"database_reachable={result.database_reachable}")
            typer.echo(f"schema_present={result.schema_present}")
            typer.echo(f"migrations_ready={result.ok}")
            if result.error:
                typer.echo(f"error={result.error}")
        if not result.ok:
            raise typer.Exit(code=1)
    finally:
        database.close()


if __name__ == "__main__":
    app()
