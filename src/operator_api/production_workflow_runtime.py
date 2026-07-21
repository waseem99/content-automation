from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.production_workflow_service import (
    ProductionWorkflowError,
    ProductionWorkflowService,
)
from src.domain.production_workflow import (
    ProductionStage,
    ReviewDecision,
    WorkflowStatus,
)
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
    visible_brand_ids,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class SnapshotPatchRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    patch: dict[str, Any]


class StageSubmitRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    rationale: str | None = Field(default=None, max_length=5000)


class ReviewDecisionRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    decision: ReviewDecision
    rationale: str = Field(min_length=3, max_length=5000)


class ReopenWorkflowRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    rationale: str = Field(min_length=3, max_length=5000)


class WorkflowAssignmentRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    assignee_operator_id: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    due_at: datetime | None = None


class WorkflowCommentRequest(BaseModel):
    workflow_version_id: UUID
    stage: ProductionStage
    comment_type: Literal["general", "change_request", "factual", "tone", "production"] = "general"
    body: str = Field(min_length=1, max_length=5000)
    parent_comment_id: UUID | None = None


def install_production_workflow_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "production_workflow_routes_installed", False):
        return
    app.state.production_workflow_routes_installed = True
    service = ProductionWorkflowService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ProductionWorkflowService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def content_brand_id(content_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    def workflow_detail(workflow_id: UUID) -> dict[str, Any]:
        try:
            return require_service().detail(workflow_id=workflow_id)
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)

    def require_workflow_access(
        workflow_id: UUID,
        operator: OperatorIdentity,
        permission: AccessPermission,
    ) -> dict[str, Any]:
        detail = workflow_detail(workflow_id)
        require_access(operator, permission, brand_id=str(detail["workflow"]["brand_id"]))
        return detail

    @app.post("/production/content/{content_id}/workflow")
    def initialize_workflow(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=content_brand_id(content_id))
        try:
            result = require_service().initialize(content_id=content_id, actor=operator.operator_id)
            detail = require_service().detail(workflow_id=result["workflow_id"])
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result, **detail}

    @app.get("/production/content/{content_id}/workflow")
    def content_workflow(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=content_brand_id(content_id))
        try:
            result = require_service().workflow_for_content(content_id=content_id)
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/production/workflows")
    def workflow_queue(
        operator: OperatorIdentity = Depends(authenticate),
        brand_id: UUID | None = None,
        stage: ProductionStage | None = None,
        status: WorkflowStatus | None = None,
        assignee: str | None = Query(default=None, max_length=120),
        overdue: bool | None = None,
        blocked: bool | None = None,
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        if brand_id is not None:
            require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
            scoped_brands: list[str] | None = [str(brand_id)]
        else:
            visible = visible_brand_ids(operator)
            scoped_brands = None if visible is None else sorted(visible)
        items = require_service().queue(
            brand_ids=scoped_brands,
            stage=stage,
            status=status,
            assignee=assignee,
            overdue=overdue,
            blocked=blocked,
        )
        return {"ok": True, "operator": operator.operator_id, "count": len(items), "items": items}

    @app.get("/production/workflows/{workflow_id}")
    def get_workflow(
        workflow_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        result = require_workflow_access(workflow_id, operator, AccessPermission.READ_PORTFOLIO)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/snapshot")
    def update_workflow_snapshot(
        workflow_id: UUID,
        request: SnapshotPatchRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        detail = workflow_detail(workflow_id)
        stage = ProductionStage(detail["workflow"]["current_stage"])
        permission = delivery_or_production_permission(stage)
        require_access(operator, permission, brand_id=str(detail["workflow"]["brand_id"]))
        try:
            result = require_service().update_snapshot(
                workflow_id=workflow_id,
                expected_lock_version=request.expected_lock_version,
                patch=request.patch,
                actor=operator.operator_id,
            )
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/submit")
    def submit_workflow_stage(
        workflow_id: UUID,
        request: StageSubmitRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        detail = workflow_detail(workflow_id)
        stage = ProductionStage(detail["workflow"]["current_stage"])
        permission = delivery_or_production_permission(stage)
        require_access(operator, permission, brand_id=str(detail["workflow"]["brand_id"]))
        try:
            result = require_service().submit(
                workflow_id=workflow_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
                rationale=request.rationale,
            )
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/decisions")
    def decide_workflow_stage(
        workflow_id: UUID,
        request: ReviewDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        detail = workflow_detail(workflow_id)
        stage = ProductionStage(detail["workflow"]["current_stage"])
        permission = AccessPermission.DELIVER_RELEASE if stage == ProductionStage.PUBLICATION else AccessPermission.REVIEW_CONTENT
        require_access(operator, permission, brand_id=str(detail["workflow"]["brand_id"]))
        try:
            result = require_service().decide(
                workflow_id=workflow_id,
                expected_lock_version=request.expected_lock_version,
                reviewer=operator.operator_id,
                decision=request.decision,
                rationale=request.rationale,
            )
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/reopen")
    def reopen_workflow(
        workflow_id: UUID,
        request: ReopenWorkflowRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_workflow_access(workflow_id, operator, AccessPermission.MANAGE_BRANDS)
        try:
            result = require_service().reopen(
                workflow_id=workflow_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
                rationale=request.rationale,
            )
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/assignments")
    def assign_workflow(
        workflow_id: UUID,
        request: WorkflowAssignmentRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_workflow_access(workflow_id, operator, AccessPermission.MANAGE_USERS)
        try:
            result = require_service().assign(
                workflow_id=workflow_id,
                expected_lock_version=request.expected_lock_version,
                assignee=request.assignee_operator_id,
                actor=operator.operator_id,
                due_at=request.due_at,
            )
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/comments")
    def add_workflow_comment(
        workflow_id: UUID,
        request: WorkflowCommentRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_workflow_access(workflow_id, operator, AccessPermission.READ_PORTFOLIO)
        try:
            result = require_service().add_comment(
                workflow_id=workflow_id,
                workflow_version_id=request.workflow_version_id,
                stage=request.stage,
                actor=operator.operator_id,
                body=request.body,
                comment_type=request.comment_type,
                parent_comment_id=request.parent_comment_id,
            )
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/production/workflows/{workflow_id}/comments/{comment_id}/resolve")
    def resolve_workflow_comment(
        workflow_id: UUID,
        comment_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_workflow_access(workflow_id, operator, AccessPermission.READ_PORTFOLIO)
        if not operator.is_admin and not (
            {OperatorRole.REVIEWER, OperatorRole.PRODUCER} & operator.roles
        ):
            raise HTTPException(status_code=403, detail="comment_resolution_permission_denied")
        try:
            result = require_service().resolve_comment(comment_id=comment_id, actor=operator.operator_id)
        except ProductionWorkflowError as exc:
            raise_workflow_error(exc)
        return {"operator": operator.operator_id, **result}


def delivery_or_production_permission(stage: ProductionStage) -> AccessPermission:
    if stage in {ProductionStage.SCHEDULING, ProductionStage.PUBLICATION}:
        return AccessPermission.DELIVER_RELEASE
    return AccessPermission.RUN_PRODUCTION


def raise_workflow_error(exc: ProductionWorkflowError) -> None:
    if exc.code.endswith("_not_found") or exc.code in {
        "content_not_found",
        "workflow_not_found",
        "workflow_version_not_found",
        "parent_comment_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "workflow_conflict",
        "independent_review_required",
        "workflow_not_active",
        "workflow_not_blocked",
        "version_not_working",
        "version_not_in_review",
        "review_snapshot_is_sealed",
        "comment_not_found_or_already_resolved",
    }:
        status_code = 409
    elif exc.code in {
        "operator_inactive_or_missing",
        "assignee_inactive_or_missing",
        "assignee_role_mismatch",
        "assignee_brand_access_denied",
    }:
        status_code = 403
    else:
        status_code = 422
    detail: dict[str, Any] = {"code": exc.code, **exc.details}
    raise HTTPException(status_code=status_code, detail=detail) from exc
