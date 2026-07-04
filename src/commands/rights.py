from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import typer

from src.application.assets.resolver import AssetResolver
from src.application.assets.storage import StorageUriResolver
from src.application.rights.enums import RightsDecisionOutcome, RightsGatePoint, RightsPlatform
from src.application.rights.gate import RightsGateService
from src.application.rights.request_models import RightsGateRequest
from src.infrastructure.database import Database, get_database_settings


app = typer.Typer(help="Evaluate canonical assets through the rights gate.")


@app.command("check")
def check(
    workflow_run: UUID = typer.Option(..., "--workflow-run"),
    asset: list[UUID] = typer.Option(..., "--asset"),
    platform: RightsPlatform = typer.Option(..., "--platform"),
    territory: str = typer.Option(..., "--territory"),
    campaign: str | None = typer.Option(None, "--campaign"),
    commercial_use: bool = typer.Option(False, "--commercial-use"),
    editorial_use: bool = typer.Option(False, "--editorial-use"),
    modification: bool = typer.Option(False, "--modification"),
    synthetic_edit: bool = typer.Option(False, "--synthetic-edit"),
    attribution: list[str] | None = typer.Option(None, "--attribution"),
    evaluated_by: str = typer.Option("operator", "--evaluated-by"),
    gate_point: RightsGatePoint = typer.Option(RightsGatePoint.MANUAL_CHECK, "--gate-point"),
    workspace_root: Path = typer.Option(Path.cwd(), "--workspace-root"),
    managed_root: Path = typer.Option(Path("data/asset_store"), "--managed-root"),
) -> None:
    supplied: dict[UUID, str] = {}
    for item in attribution or []:
        asset_id, separator, text = item.partition("=")
        if not separator:
            raise typer.BadParameter("Attribution must use ASSET_UUID=text")
        supplied[UUID(asset_id)] = text

    root = workspace_root.expanduser().resolve()
    managed = managed_root.expanduser()
    managed = managed.resolve() if managed.is_absolute() else (root / managed).resolve()

    database = Database(get_database_settings())
    database.open()
    try:
        resolver = AssetResolver(database, StorageUriResolver(root, managed))
        gate = RightsGateService(database=database, asset_resolver=resolver)
        decision = gate.evaluate(
            RightsGateRequest(
                workflow_run_id=workflow_run,
                gate_point=gate_point,
                asset_ids=tuple(asset),
                platform=platform,
                territory=territory,
                campaign=campaign,
                commercial_use=commercial_use,
                editorial_use=editorial_use,
                modification=modification,
                synthetic_edit=synthetic_edit,
                supplied_attribution=supplied,
                evaluated_by=evaluated_by,
            )
        )
        typer.echo(json.dumps(decision.model_dump(mode="json"), indent=2))
        if decision.outcome == RightsDecisionOutcome.HUMAN_REVIEW_REQUIRED:
            raise typer.Exit(code=2)
        if decision.outcome == RightsDecisionOutcome.BLOCK:
            raise typer.Exit(code=3)
    finally:
        database.close()


if __name__ == "__main__":
    app()
