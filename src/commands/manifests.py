from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import typer

from src.application.assets.resolver import AssetResolver
from src.application.assets.storage import StorageUriResolver
from src.application.manifests.builder import RenderManifestBuilder
from src.application.manifests.integrity import ManifestIntegrityVerifier
from src.application.manifests.models import RenderManifestBuildRequest
from src.infrastructure.database import Database, get_database_settings
from src.infrastructure.database.uow import unit_of_work


app = typer.Typer(help="Build and verify immutable render manifests.")


@app.command("build")
def build(request_file: Path = typer.Option(..., "--request")) -> None:
    request = RenderManifestBuildRequest.model_validate_json(
        request_file.read_text(encoding="utf-8")
    )
    database = Database(get_database_settings())
    database.open()
    try:
        record = RenderManifestBuilder(database).build(request)
        typer.echo(record.model_dump_json(indent=2))
    finally:
        database.close()


@app.command("show")
def show(manifest_id: UUID = typer.Option(..., "--manifest")) -> None:
    database = Database(get_database_settings())
    database.open()
    try:
        with unit_of_work(database) as uow:
            record = uow.render_manifests.get(manifest_id)
        typer.echo(record.model_dump_json(indent=2))
    finally:
        database.close()


@app.command("verify")
def verify(
    manifest_id: UUID = typer.Option(..., "--manifest"),
    workspace_root: Path = typer.Option(Path.cwd(), "--workspace-root"),
    managed_root: Path = typer.Option(Path("data/asset_store"), "--managed-root"),
) -> None:
    root = workspace_root.expanduser().resolve()
    managed = managed_root.expanduser()
    managed = managed.resolve() if managed.is_absolute() else (root / managed).resolve()

    database = Database(get_database_settings())
    database.open()
    try:
        resolver = AssetResolver(database, StorageUriResolver(root, managed))
        record, paths = ManifestIntegrityVerifier(database, resolver).verify(manifest_id)
        typer.echo(
            json.dumps(
                {
                    "manifest_id": str(record.id),
                    "manifest_hash": record.manifest_hash,
                    "mode": record.document.mode.value,
                    "verified_assets": {str(key): value for key, value in paths.items()},
                    "not_for_publication": record.document.not_for_publication,
                },
                indent=2,
            )
        )
    finally:
        database.close()


if __name__ == "__main__":
    app()
