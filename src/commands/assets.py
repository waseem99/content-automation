from __future__ import annotations

import json
from pathlib import Path

import typer

from src.application.assets.backfill import BackfillService, DEFAULT_EXCLUDES
from src.application.assets.registry import AssetRegistryService
from src.application.assets.storage import ManagedAssetStore, StorageUriResolver
from src.infrastructure.database import Database, get_database_settings


app = typer.Typer(help="Canonical asset registry operations.")


def _services(workspace_root: Path, managed_root: Path) -> tuple[Database, BackfillService]:
    database = Database(get_database_settings())
    database.open()
    resolver = StorageUriResolver(workspace_root=workspace_root, managed_root=managed_root)
    registry = AssetRegistryService(
        database=database,
        storage_resolver=resolver,
        managed_store=ManagedAssetStore(resolver),
    )
    return database, BackfillService(database=database, registry=registry)


@app.command("backfill")
def backfill(
    root: Path = typer.Option(Path("data"), "--root", exists=True, file_okay=False),
    dry_run: bool = typer.Option(False, "--dry-run"),
    commit: bool = typer.Option(False, "--commit"),
    include: list[str] | None = typer.Option(None, "--include"),
    exclude: list[str] | None = typer.Option(None, "--exclude"),
    max_files: int | None = typer.Option(None, "--max-files", min=1),
    report_path: Path | None = typer.Option(None, "--report-path"),
    created_by: str | None = typer.Option(None, "--created-by"),
    continue_on_error: bool = typer.Option(False, "--continue-on-error"),
    managed_root: Path = typer.Option(Path("data/asset_store"), "--managed-root"),
) -> None:
    if dry_run == commit:
        raise typer.BadParameter("Choose exactly one of --dry-run or --commit")

    workspace_root = Path.cwd().resolve()
    resolved_root = root.expanduser().resolve()
    report = report_path or resolved_root / "asset-backfill-report.json"
    database, service = _services(workspace_root, managed_root)
    try:
        result = service.run(
            root=resolved_root,
            commit=commit,
            include=tuple(include or ()),
            exclude=tuple(exclude or DEFAULT_EXCLUDES),
            max_files=max_files,
            created_by=created_by,
            continue_on_error=continue_on_error,
            report_path=report,
        )
        counts: dict[str, int] = {}
        for entry in result.entries:
            counts[entry.action] = counts.get(entry.action, 0) + 1
        typer.echo(json.dumps({"report": str(report), "counts": counts}, indent=2))
        if counts.get("conflict"):
            raise typer.Exit(code=2)
    finally:
        database.close()


@app.command("verify")
def verify(
    root: Path = typer.Option(Path("data"), "--root", exists=True, file_okay=False),
    managed_root: Path = typer.Option(Path("data/asset_store"), "--managed-root"),
    report_path: Path | None = typer.Option(None, "--report-path"),
) -> None:
    workspace_root = Path.cwd().resolve()
    resolved_root = root.expanduser().resolve()
    report = report_path or resolved_root / "asset-verification-report.json"
    database, service = _services(workspace_root, managed_root)
    try:
        result = service.run(root=resolved_root, commit=False, report_path=report)
        unresolved = [entry for entry in result.entries if entry.action != "deduplicate"]
        typer.echo(
            json.dumps(
                {
                    "report": str(report),
                    "verified": len(result.entries) - len(unresolved),
                    "unresolved": len(unresolved),
                },
                indent=2,
            )
        )
        if unresolved:
            raise typer.Exit(code=1)
    finally:
        database.close()


if __name__ == "__main__":
    app()
