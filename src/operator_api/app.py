from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.application.p4_audit import P4AuditReportService
from src.application.p4_dashboard import P4DashboardContracts
from src.application.p4_demo_flow import P4DemoFlowService
from src.application.p4_surface import P4OperatorSurface
from src.infrastructure.database.connection import Database


class WorkflowRunRequest(BaseModel):
    topic: str
    source_urls: list[str] = Field(default_factory=list)
    actor: str = "operator"


class ApprovalRequest(BaseModel):
    action: str
    resource_id: UUID
    reviewed_by: str = "operator"
    rationale: str | None = None


class DemoApprovalRequest(BaseModel):
    reviewed_by: str = "operator"
    rationale: str | None = None


def create_app(database: Database | None = None) -> FastAPI:
    app = FastAPI(title="Content Automation Operator API", version="0.5.0")
    app.state.database = database

    @app.get("/health")
    def health() -> dict[str, Any]:
        db = _database_or_none(app)
        return {
            "ok": True,
            "service": "content-automation-operator-api",
            "version": "0.5.0",
            "database_configured": db is not None,
        }

    @app.post("/workflows/{workflow_run_id}/run")
    def run_workflow(workflow_run_id: UUID, request: WorkflowRunRequest) -> dict[str, Any]:
        return P4OperatorSurface(_database(app)).run_workflow(
            workflow_run_id=workflow_run_id,
            topic=request.topic,
            source_urls=tuple(request.source_urls),
            actor=request.actor,
        )

    @app.get("/workflows/{workflow_run_id}/queue")
    def queue(workflow_run_id: UUID) -> dict[str, Any]:
        return P4OperatorSurface(_database(app)).queue(workflow_run_id=workflow_run_id)

    @app.get("/workflows/{workflow_run_id}/dashboard/queue")
    def dashboard_queue(workflow_run_id: UUID) -> dict[str, Any]:
        return P4DashboardContracts(_database(app)).queue_cards(workflow_run_id=workflow_run_id)

    @app.get("/workflows/{workflow_run_id}/dashboard/schema")
    def dashboard_schema(workflow_run_id: UUID) -> dict[str, Any]:
        return {"workflow_run_id": str(workflow_run_id), **P4DashboardContracts(_database(app)).schema()}

    @app.post("/workflows/{workflow_run_id}/approvals")
    def approval_action(workflow_run_id: UUID, request: ApprovalRequest) -> dict[str, Any]:
        return P4DashboardContracts(_database(app)).approval_action(
            action=request.action,
            workflow_run_id=workflow_run_id,
            resource_id=request.resource_id,
            reviewed_by=request.reviewed_by,
            rationale=request.rationale,
        )

    @app.get("/workflows/{workflow_run_id}/audit")
    def audit(workflow_run_id: UUID) -> dict[str, Any]:
        return P4AuditReportService(_database(app)).report(workflow_run_id=workflow_run_id)

    @app.get("/demo/scenario")
    def demo_scenario() -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).scenario()

    @app.post("/demo/{workflow_run_id}/start")
    def demo_start(workflow_run_id: UUID) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).start(workflow_run_id=workflow_run_id)

    @app.post("/demo/{workflow_run_id}/approve-current")
    def demo_approve_current(workflow_run_id: UUID, request: DemoApprovalRequest) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).approve_current(
            workflow_run_id=workflow_run_id,
            reviewed_by=request.reviewed_by,
            rationale=request.rationale,
        )

    @app.get("/demo/{workflow_run_id}/status")
    def demo_status(workflow_run_id: UUID) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).status(workflow_run_id=workflow_run_id)

    return app


def _database_or_none(app: FastAPI) -> Database | None:
    value = getattr(app.state, "database", None)
    return value if isinstance(value, Database) else None


def _database(app: FastAPI) -> Database:
    database = _database_or_none(app)
    if database is None:
        raise RuntimeError("operator API database is not configured")
    return database
