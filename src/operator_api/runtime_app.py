from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from src.application.p4_audit import P4AuditReportService
from src.application.p4_dashboard import P4DashboardContracts
from src.application.p4_demo_flow import P4DemoFlowService
from src.application.p4_surface import P4OperatorSurface
from src.infrastructure.database.connection import Database
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class WorkflowRunRequest(BaseModel):
    topic: str
    source_urls: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    action: str
    resource_id: UUID
    rationale: str | None = None


class DemoApprovalRequest(BaseModel):
    rationale: str | None = None


def create_app(database: Database | None = None, auth_settings: OperatorAuthSettings | None = None) -> FastAPI:
    app = FastAPI(title="Content Automation Operator API", version="0.5.0")
    app.state.database = database
    app.state.auth_settings = auth_settings or OperatorAuthSettings()
    require_operator = build_operator_auth(app.state.auth_settings)

    @app.get("/health")
    def health() -> dict[str, Any]:
        db = _database_or_none(app)
        auth = _auth_settings(app)
        return {"ok": True, "service": "content-automation-operator-api", "version": "0.5.0", "database_configured": db is not None, "auth_required": not auth.disabled}

    @app.post("/workflows/{workflow_run_id}/run")
    def run_workflow(workflow_run_id: UUID, request: WorkflowRunRequest, operator=Depends(require_operator)) -> dict[str, Any]:
        return P4OperatorSurface(_database(app)).run_workflow(workflow_run_id=workflow_run_id, topic=request.topic, source_urls=tuple(request.source_urls), actor=operator.operator_id)

    @app.get("/workflows/{workflow_run_id}/queue")
    def queue(workflow_run_id: UUID, operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4OperatorSurface(_database(app)).queue(workflow_run_id=workflow_run_id)}

    @app.get("/workflows/{workflow_run_id}/dashboard/queue")
    def dashboard_queue(workflow_run_id: UUID, operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4DashboardContracts(_database(app)).queue_cards(workflow_run_id=workflow_run_id)}

    @app.get("/workflows/{workflow_run_id}/dashboard/schema")
    def dashboard_schema(workflow_run_id: UUID, operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, "workflow_run_id": str(workflow_run_id), **P4DashboardContracts(_database(app)).schema()}

    @app.post("/workflows/{workflow_run_id}/approvals")
    def approval_action(workflow_run_id: UUID, request: ApprovalRequest, operator=Depends(require_operator)) -> dict[str, Any]:
        return P4DashboardContracts(_database(app)).approval_action(action=request.action, workflow_run_id=workflow_run_id, resource_id=request.resource_id, reviewed_by=operator.operator_id, rationale=request.rationale)

    @app.get("/workflows/{workflow_run_id}/audit")
    def audit(workflow_run_id: UUID, operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4AuditReportService(_database(app)).report(workflow_run_id=workflow_run_id)}

    @app.get("/demo/scenario")
    def demo_scenario(operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4DemoFlowService(_database(app)).scenario()}

    @app.post("/demo/{workflow_run_id}/start")
    def demo_start(workflow_run_id: UUID, operator=Depends(require_operator)) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).start(workflow_run_id=workflow_run_id)

    @app.post("/demo/{workflow_run_id}/approve-current")
    def demo_approve_current(workflow_run_id: UUID, request: DemoApprovalRequest, operator=Depends(require_operator)) -> dict[str, Any]:
        return P4DemoFlowService(_database(app)).approve_current(workflow_run_id=workflow_run_id, reviewed_by=operator.operator_id, rationale=request.rationale)

    @app.get("/demo/{workflow_run_id}/status")
    def demo_status(workflow_run_id: UUID, operator=Depends(require_operator)) -> dict[str, Any]:
        return {"operator": operator.operator_id, **P4DemoFlowService(_database(app)).status(workflow_run_id=workflow_run_id)}

    return app


def _auth_settings(app: FastAPI) -> OperatorAuthSettings:
    value = getattr(app.state, "auth_settings", None)
    return value if isinstance(value, OperatorAuthSettings) else OperatorAuthSettings()


def _database_or_none(app: FastAPI) -> Database | None:
    value = getattr(app.state, "database", None)
    return value if isinstance(value, Database) else None


def _database(app: FastAPI) -> Database:
    database = _database_or_none(app)
    if database is None:
        raise RuntimeError("operator API database is not configured")
    return database
