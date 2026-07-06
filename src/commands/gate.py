from __future__ import annotations

import json
from uuid import UUID

import typer

from src.application.gates import OperatorGateService
from src.domain.human_review_models import ReviewDecision, ReviewDecisionCreate, ReviewRequestCreate, ReviewTargetType
from src.infrastructure.database import Database, get_database_settings


app = typer.Typer(help="Create and decide operator gates.")


def _database() -> Database:
    database = Database(get_database_settings())
    database.open()
    return database


@app.command("request")
def request_gate(
    workflow_id: UUID = typer.Option(..., "--workflow"),
    stage_id: UUID | None = typer.Option(None, "--stage"),
    target_type: ReviewTargetType = typer.Option(..., "--target-type"),
    target_id: UUID | None = typer.Option(None, "--target-id"),
    review_type: str = typer.Option(..., "--type"),
    requested_by: str = typer.Option(..., "--requested-by"),
    reason: str = typer.Option(..., "--reason"),
) -> None:
    database = _database()
    try:
        result = OperatorGateService(database).request_gate(
            ReviewRequestCreate(
                workflow_run_id=workflow_id,
                stage_execution_id=stage_id,
                target_type=target_type,
                target_id=target_id,
                review_type=review_type,
                requested_by=requested_by,
                reason=reason,
            )
        )
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:
        database.close()


@app.command("decide")
def decide(
    workflow_id: UUID = typer.Option(..., "--workflow"),
    request_id: UUID = typer.Option(..., "--request"),
    decision: ReviewDecision = typer.Option(..., "--decision"),
    reviewer: str = typer.Option(..., "--reviewer"),
    rationale: str = typer.Option(..., "--rationale"),
    checklist_json: str = typer.Option(..., "--checklist-json"),
) -> None:
    database = _database()
    try:
        checklist = json.loads(checklist_json)
        result = OperatorGateService(database).record_decision(
            ReviewDecisionCreate(
                workflow_run_id=workflow_id,
                review_request_id=request_id,
                review_type="operator_gate",
                decision=decision,
                reviewer=reviewer,
                rationale=rationale,
                checklist=checklist,
            )
        )
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:
        database.close()


@app.command("history")
def history(workflow_id: UUID = typer.Option(..., "--workflow")) -> None:
    database = _database()
    try:
        result = OperatorGateService(database).history_for_workflow(workflow_id)
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    app()
