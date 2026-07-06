from __future__ import annotations

import json
from pathlib import Path

import typer

from src.application.observability.health import HealthCheckService
from src.application.secrets.provider import EnvSecretProvider, RuntimeEnvironment, SecretRequirement, SecretValidator
from src.application.storage.provider import LocalStorageProvider
from src.infrastructure.database import Database, get_database_settings


app = typer.Typer(help="Health and readiness checks.")


def _database() -> Database:
    database = Database(get_database_settings())
    database.open(require_schema=False)
    return database


@app.command("readiness")
def readiness(root: Path = typer.Option(..., "--storage-root"), required_secret: list[str] = typer.Option([], "--required-secret")) -> None:
    database = _database()
    try:
        service = HealthCheckService(
            database=database,
            storage=LocalStorageProvider(root),
            secrets=SecretValidator(EnvSecretProvider(), environment=RuntimeEnvironment.LOCAL),
        )
        report = service.readiness(requirements=tuple(SecretRequirement(name=name) for name in required_secret))
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0 if report.ok else 1)
    finally:
        database.close()


@app.command("health")
def health(root: Path = typer.Option(..., "--storage-root")) -> None:
    database = _database()
    try:
        report = HealthCheckService(database=database, storage=LocalStorageProvider(root)).health()
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0 if report.ok else 1)
    finally:
        database.close()


if __name__ == "__main__":
    app()
