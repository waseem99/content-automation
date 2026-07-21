from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from src.operations.backup import BackupRestoreError, BackupRestoreManager
from src.operations.settings import OperationsSettings


app = typer.Typer(help="Production operations backup and restore utilities.")


def _manager(environment: str, database_url: str | None) -> BackupRestoreManager:
    resolved_url = database_url or os.environ.get("DATABASE_URL")
    if not resolved_url:
        raise typer.BadParameter("DATABASE_URL or --database-url is required")
    return BackupRestoreManager(database_url=resolved_url, environment=environment)


def _emit(payload: dict) -> None:
    typer.echo(json.dumps(payload, sort_keys=True, default=str))


@app.command("database-backup")
def database_backup(
    destination: Path = typer.Option(..., dir_okay=False, writable=True),
    environment: str = typer.Option("staging"),
    database_url: str | None = typer.Option(None, envvar="DATABASE_URL", hidden=True),
) -> None:
    try:
        backup = _manager(environment, database_url).create_database_backup(destination)
    except BackupRestoreError as exc:
        raise typer.Exit(code=1) from exc
    _emit({"path": str(backup.path), "sha256": backup.sha256, "size_bytes": backup.size_bytes})


@app.command("artifact-backup")
def artifact_backup(
    root: Path = typer.Option(..., exists=True, file_okay=False, readable=True),
    destination: Path = typer.Option(..., dir_okay=False, writable=True),
    environment: str = typer.Option("staging"),
    database_url: str | None = typer.Option(None, envvar="DATABASE_URL", hidden=True),
) -> None:
    try:
        backup, manifest = _manager(environment, database_url).create_artifact_backup(
            root,
            destination,
        )
    except BackupRestoreError as exc:
        raise typer.Exit(code=1) from exc
    _emit(
        {
            "path": str(backup.path),
            "sha256": backup.sha256,
            "size_bytes": backup.size_bytes,
            "object_count": len(manifest),
        }
    )


@app.command("database-restore-drill")
def database_restore_drill(
    backup: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    expected_sha256: str = typer.Option(..., min=64, max=64),
    expected_migration_head: str = typer.Option(..., min=8, max=200),
    environment: str = typer.Option("staging"),
    allow_destructive_drill: bool = typer.Option(False, "--allow-destructive-drill"),
    database_url: str | None = typer.Option(None, envvar="DATABASE_URL", hidden=True),
) -> None:
    manager = _manager(environment, database_url)
    try:
        restored = manager.restore_database_backup(
            backup,
            expected_sha256=expected_sha256,
            allow_destructive_drill=allow_destructive_drill,
        )
        verification = manager.verify_database_schema(expected_migration_head)
    except BackupRestoreError as exc:
        raise typer.Exit(code=1) from exc
    _emit(
        {
            "path": str(restored.path),
            "sha256": restored.sha256,
            "size_bytes": restored.size_bytes,
            "verification": verification,
        }
    )


@app.command("artifact-restore-drill")
def artifact_restore_drill(
    backup: Path = typer.Option(..., exists=True, dir_okay=False, readable=True),
    destination: Path = typer.Option(..., file_okay=False),
    expected_sha256: str = typer.Option(..., min=64, max=64),
    environment: str = typer.Option("staging"),
    allow_destructive_drill: bool = typer.Option(False, "--allow-destructive-drill"),
    database_url: str | None = typer.Option(None, envvar="DATABASE_URL", hidden=True),
) -> None:
    try:
        result = _manager(environment, database_url).restore_artifact_backup(
            backup,
            destination,
            expected_sha256=expected_sha256,
            allow_destructive_drill=allow_destructive_drill,
        )
    except BackupRestoreError as exc:
        raise typer.Exit(code=1) from exc
    _emit(result)


@app.command("validate-settings")
def validate_settings() -> None:
    settings = OperationsSettings()
    _emit(settings.public_snapshot())


if __name__ == "__main__":
    app()
