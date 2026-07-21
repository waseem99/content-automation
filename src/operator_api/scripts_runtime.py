from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.application.scripts.models import (
    ReplaceScriptDraftRequest,
    ScriptDecisionRequest,
    ScriptGenerateRequest,
    ScriptReviewActionRequest,
    ScriptRevisionRequest,
    SourceSupportUpdateRequest,
    SubmitScriptRequest,
)
from src.application.scripts.service import ScriptReviewError, ScriptReviewService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class CreateReviewActionRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)
    action: ScriptReviewActionRequest


class ResolveReviewActionRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)


def install_script_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "script_routes_installed", False):
        return
    app.state.script_routes_installed = True
    service = ScriptReviewService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ScriptReviewService:
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
                """SELECT mp.brand_id
                   FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    def document_brand_id(document_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.script_documents sd
                   JOIN football_brief.portfolio_content pc ON pc.id=sd.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE sd.id=%s""",
                (document_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="script_document_not_found")
        return str(row["brand_id"])

    @app.post("/scripts/content/{content_id}")
    def initialize_script(
        content_id: UUID,
        request: ScriptGenerateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(content_id),
        )
        try:
            result = require_service().initialize(
                content_id=content_id,
                request=request,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/scripts/content/{content_id}")
    def get_content_script(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=content_brand_id(content_id),
        )
        try:
            result = require_service().document_for_content(content_id=content_id)
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/scripts/{document_id}")
    def get_script_document(
        document_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().detail(document_id=document_id)
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/draft")
    def replace_script_draft(
        document_id: UUID,
        request: ReplaceScriptDraftRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().replace_working_draft(
                document_id=document_id,
                expected_lock_version=request.expected_lock_version,
                draft=request.draft,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/sources")
    def update_script_sources(
        document_id: UUID,
        request: SourceSupportUpdateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().update_source_support(
                document_id=document_id,
                request=request,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/submit")
    def submit_script(
        document_id: UUID,
        request: SubmitScriptRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().submit(
                document_id=document_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/review-actions")
    def create_script_review_action(
        document_id: UUID,
        request: CreateReviewActionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().add_review_action(
                document_id=document_id,
                expected_lock_version=request.expected_lock_version,
                request=request.action,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/review-actions/{action_id}/resolve")
    def resolve_script_review_action(
        document_id: UUID,
        action_id: UUID,
        request: ResolveReviewActionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = document_brand_id(document_id)
        if operator.is_admin or OperatorRole.REVIEWER in operator.roles:
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        else:
            raise HTTPException(status_code=403, detail="script_review_resolution_permission_denied")
        try:
            result = require_service().resolve_review_action(
                document_id=document_id,
                action_id=action_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/decisions")
    def decide_script(
        document_id: UUID,
        request: ScriptDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().decide(
                document_id=document_id,
                expected_lock_version=request.expected_lock_version,
                decision=request.decision,
                rationale=request.rationale,
                reviewer=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/scripts/{document_id}/revise")
    def revise_script(
        document_id: UUID,
        request: ScriptRevisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=document_brand_id(document_id),
        )
        try:
            result = require_service().revise(
                document_id=document_id,
                expected_lock_version=request.expected_lock_version,
                reason=request.reason,
                actor=operator.operator_id,
            )
        except ScriptReviewError as exc:
            raise_script_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_script_error(exc: ScriptReviewError) -> None:
    if exc.code in {
        "content_or_workflow_not_found",
        "script_document_not_found",
        "script_review_action_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "script_document_conflict",
        "script_version_not_working",
        "script_version_not_in_review",
        "script_version_not_revisable",
        "stale_script_version",
        "stale_script_review_action",
        "script_review_action_already_resolved",
        "workflow_not_ready_for_script",
    }:
        status_code = 409
    elif exc.code in {
        "operator_inactive_or_missing",
        "active_brand_profile_required",
    }:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
