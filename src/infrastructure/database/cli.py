from __future__ import annotations

import json
from uuid import UUID

import typer

from src.application.intake_service import CreateIntakeRequest, IntakeValidationError, SourceIntakeService
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations, migration_status
from src.infrastructure.database.settings import get_database_settings

app = typer.Typer(help="Football Brief database commands")
intake_app = typer.Typer(help="Content intake commands")


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


@intake_app.command("create")
def intake_create(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    topic: str | None = typer.Option(None, "--topic"),
    url: list[str] | None = typer.Option(None, "--url"),
    angle: str | None = typer.Option(None, "--angle"),
    created_by: str = typer.Option("operator", "--created-by"),
    team: str | None = typer.Option(None, "--team"),
    player: str | None = typer.Option(None, "--player"),
    league: str | None = typer.Option(None, "--league"),
    match: str | None = typer.Option(None, "--match"),
    season: str | None = typer.Option(None, "--season"),
    competition: str | None = typer.Option(None, "--competition"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        metadata = {
            key: value
            for key, value in {
                "team": team,
                "player": player,
                "league": league,
                "match": match,
                "season": season,
                "competition": competition,
            }.items()
            if value
        }
        result = SourceIntakeService(database).create(
            CreateIntakeRequest(
                workflow_run_id=UUID(workflow_run_id),
                topic=topic,
                angle=angle,
                source_urls=tuple(url or ()),
                created_by=created_by,
                football_metadata=metadata,
            )
        )
        payload = {
            "id": str(result.intake.id),
            "created": result.created,
            "canonical_input_hash": result.intake.canonical_input_hash,
            "reference_count": len(result.references),
        }
        typer.echo(json.dumps(payload, indent=2) if output_json else str(payload))
    except (ValueError, IntakeValidationError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    finally:
        database.close()


@intake_app.command("list")
def intake_list(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        rows = SourceIntakeService(database).list_for_workflow(UUID(workflow_run_id))
        payload = [
            {
                "id": str(row.id),
                "topic": row.topic,
                "angle": row.angle,
                "status": row.status,
                "canonical_input_hash": row.canonical_input_hash,
                "created_by": row.created_by,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
        typer.echo(json.dumps(payload, indent=2) if output_json else "\n".join(str(item) for item in payload))
    finally:
        database.close()


app.add_typer(intake_app, name="intake")


if __name__ == "__main__":
    app()
