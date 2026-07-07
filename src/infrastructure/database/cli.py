from __future__ import annotations

import json
from uuid import UUID

import typer

from src.application.intake_service import CreateIntakeRequest, IntakeValidationError, SourceIntakeService
from src.application.operator_review_tools import OperatorReviewTools
from src.infrastructure.database.connection import Database
from src.infrastructure.database.migrations import apply_migrations, migration_status
from src.infrastructure.database.settings import get_database_settings

app = typer.Typer(help="Football Brief database commands")
intake_app = typer.Typer(help="Content intake commands")
operator_app = typer.Typer(help="Operator review commands")


def _open() -> tuple[object, Database]:
    settings = get_database_settings()
    database = Database(settings)
    database.open(require_schema=False)
    return settings, database


def _json_default(value: object) -> str:
    return str(value)


def _emit(payload: object, output_json: bool) -> None:
    typer.echo(json.dumps(payload, indent=2, default=_json_default) if output_json else str(payload))


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
        _emit(payload, output_json)
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
        _emit(payload, output_json)
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
        _emit(payload, output_json)
    finally:
        database.close()


@operator_app.command("queue")
def operator_queue(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        rows = OperatorReviewTools(database).queue(UUID(workflow_run_id))
        payload = [
            {
                "type": row.item_type,
                "id": str(row.id),
                "workflow_run_id": str(row.workflow_run_id),
                "status": row.status,
                "title": row.title,
                "created_at": row.created_at.isoformat(),
                "metadata": row.metadata,
            }
            for row in rows
        ]
        _emit(payload, output_json)
    finally:
        database.close()


@operator_app.command("approve-packet")
def operator_approve_packet(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    packet_id: str = typer.Option(..., "--packet-id"),
    reviewed_by: str = typer.Option("operator", "--reviewed-by"),
    rationale: str | None = typer.Option(None, "--rationale"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).approve_packet(
            workflow_run_id=UUID(workflow_run_id),
            packet_id=UUID(packet_id),
            reviewed_by=reviewed_by,
            rationale=rationale,
        )
        _emit({"id": str(row.id), "packet_id": str(row.packet_id), "status": row.status, "reviewed_by": row.reviewed_by}, output_json)
    finally:
        database.close()


@operator_app.command("request-output")
def operator_request_output(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    source_output_id: str = typer.Option(..., "--source-output-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).request_output_review(
            workflow_run_id=UUID(workflow_run_id),
            source_output_id=UUID(source_output_id),
        )
        _emit({"id": str(row.id), "source_output_id": str(row.source_output_id), "status": row.status}, output_json)
    finally:
        database.close()


@operator_app.command("approve-output")
def operator_approve_output(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    source_output_id: str = typer.Option(..., "--source-output-id"),
    reviewed_by: str = typer.Option("operator", "--reviewed-by"),
    rationale: str | None = typer.Option(None, "--rationale"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).approve_output(
            workflow_run_id=UUID(workflow_run_id),
            source_output_id=UUID(source_output_id),
            reviewed_by=reviewed_by,
            rationale=rationale,
        )
        _emit({"id": str(row.id), "source_output_id": str(row.source_output_id), "status": row.status, "reviewed_by": row.reviewed_by}, output_json)
    finally:
        database.close()


@operator_app.command("request-option")
def operator_request_option(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    option_id: str = typer.Option(..., "--option-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).request_option_review(workflow_run_id=UUID(workflow_run_id), option_id=UUID(option_id))
        _emit({"id": str(row.id), "option_id": str(row.option_id), "status": row.status}, output_json)
    finally:
        database.close()


@operator_app.command("approve-option")
def operator_approve_option(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    option_id: str = typer.Option(..., "--option-id"),
    reviewed_by: str = typer.Option("operator", "--reviewed-by"),
    rationale: str | None = typer.Option(None, "--rationale"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).approve_option(
            workflow_run_id=UUID(workflow_run_id),
            option_id=UUID(option_id),
            reviewed_by=reviewed_by,
            rationale=rationale,
        )
        _emit({"id": str(row.id), "option_id": str(row.option_id), "status": row.status, "reviewed_by": row.reviewed_by}, output_json)
    finally:
        database.close()


@operator_app.command("request-package")
def operator_request_package(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    package_id: str = typer.Option(..., "--package-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).request_package_review(workflow_run_id=UUID(workflow_run_id), package_id=UUID(package_id))
        _emit({"id": str(row.id), "package_id": str(row.package_id), "status": row.status}, output_json)
    finally:
        database.close()


@operator_app.command("approve-package")
def operator_approve_package(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    package_id: str = typer.Option(..., "--package-id"),
    reviewed_by: str = typer.Option("operator", "--reviewed-by"),
    rationale: str | None = typer.Option(None, "--rationale"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        row = OperatorReviewTools(database).approve_package(
            workflow_run_id=UUID(workflow_run_id),
            package_id=UUID(package_id),
            reviewed_by=reviewed_by,
            rationale=rationale,
        )
        _emit({"id": str(row.id), "package_id": str(row.package_id), "status": row.status, "reviewed_by": row.reviewed_by}, output_json)
    finally:
        database.close()


@operator_app.command("package-status")
def operator_package_status(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    package_id: str = typer.Option(..., "--package-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        payload = OperatorReviewTools(database).package_status(workflow_run_id=UUID(workflow_run_id), package_id=UUID(package_id))
        _emit(payload, output_json)
    finally:
        database.close()


@operator_app.command("manifest-status")
def operator_manifest_status(
    workflow_run_id: str = typer.Option(..., "--workflow-run-id"),
    package_id: str | None = typer.Option(None, "--package-id"),
    output_json: bool = typer.Option(False, "--json"),
) -> None:
    _settings, database = _open()
    try:
        payload = OperatorReviewTools(database).manifest_status(
            workflow_run_id=UUID(workflow_run_id),
            package_id=UUID(package_id) if package_id else None,
        )
        _emit(payload, output_json)
    finally:
        database.close()


app.add_typer(intake_app, name="intake")
app.add_typer(operator_app, name="operator")


if __name__ == "__main__":
    app()
