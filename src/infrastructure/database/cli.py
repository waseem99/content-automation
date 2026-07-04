from __future__ import annotations

import json

import typer

from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations, migration_status
from src.infrastructure.database.settings import get_database_settings

app = typer.Typer(help="Football Brief database commands")


def _open() -> tuple[object, Database]:
    settings = get_database_settings()
    database = Database(settings)
    database.open(require_schema=False)
    return settings, database


@app.command()
def migrate() -> None:
    settings, database = _open()
    try:
        applied = apply_migrations(database, settings.migrations_dir)
        typer.echo("\n".join(applied) if applied else "Database is already up to date.")
    finally:
        database.close()


@app.command()
def status() -> None:
    settings, database = _open()
    try:
        failed = False
        for row in migration_status(database, settings.migrations_dir):
            label = "PENDING" if not row.applied else "APPLIED"
            if row.applied and not row.checksum_matches:
                label = "CHECKSUM_MISMATCH"
                failed = True
            typer.echo(f"{label:18} {row.filename}")
        if failed:
            raise typer.Exit(code=2)
    finally:
        database.close()


@app.command()
def health(output_json: bool = typer.Option(False, "--json")) -> None:
    settings, database = _open()
    try:
        result = database.health_check(settings.migrations_dir)
        payload = {
            "ok": result.ok,
            "database_reachable": result.database_reachable,
            "schema_present": result.schema_present,
            "migrations_table_present": result.migrations_table_present,
            "applied_migrations": list(result.applied_migrations),
            "expected_migrations": list(result.expected_migrations),
            "error": result.error,
        }
        typer.echo(json.dumps(payload, indent=2) if output_json else str(payload))
        if not result.ok:
            raise typer.Exit(code=1)
    finally:
        database.close()


if __name__ == "__main__":
    app()
