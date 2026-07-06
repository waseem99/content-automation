from __future__ import annotations

import json
from uuid import UUID

import typer

from src.infrastructure.database import Database, get_database_settings
from src.infrastructure.database.repository_provider_generation import ProviderGenerationEvidenceRepository
from src.infrastructure.database.uow import unit_of_work


app = typer.Typer(help="Inspect asset lineage and provider-generation evidence.")


@app.command("show")
def show(asset_id: UUID = typer.Option(..., "--asset")) -> None:
    database = Database(get_database_settings())
    database.open()
    try:
        with unit_of_work(database) as uow:
            report = ProviderGenerationEvidenceRepository(uow.conn).lineage_for_asset(asset_id)
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    app()
