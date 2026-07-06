from __future__ import annotations

import json
from pathlib import Path

import typer

from src.application.storage.models import AccessLevel, SignedUrlRequest, StoragePurpose
from src.application.storage.provider import LocalStorageProvider
from src.application.storage.temp import TemporaryFileManager


app = typer.Typer(help="Storage utility commands.")


@app.command("cleanup-temp")
def cleanup_temp(root: Path = typer.Option(..., "--root"), retention_seconds: int = typer.Option(86_400, "--retention-seconds")) -> None:
    storage = LocalStorageProvider(root)
    summary = TemporaryFileManager(storage, retention_seconds=retention_seconds).cleanup_expired()
    typer.echo(json.dumps(summary.model_dump(mode="json"), indent=2))


@app.command("sign-url")
def sign_url(
    root: Path = typer.Option(..., "--root"),
    uri: str = typer.Option(..., "--uri"),
    purpose: StoragePurpose = typer.Option(..., "--purpose"),
    access: AccessLevel = typer.Option(AccessLevel.INTERNAL, "--access"),
    expires_in_seconds: int = typer.Option(900, "--expires-in-seconds"),
) -> None:
    storage = LocalStorageProvider(root)
    result = storage.signed_url(SignedUrlRequest(uri=uri, purpose=purpose, access_level=access, expires_in_seconds=expires_in_seconds))
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    app()
