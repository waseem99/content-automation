from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.review_workspace.models import (
    CompareTarget,
    InboxFilters,
    ReviewCommentRequest,
    ReviewTarget,
    TaskMutationRequest,
)
from src.application.review_workspace.service import ReviewWorkspaceError
from src.application.review_workspace.validated_service import ValidatedReviewWorkspaceService
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


def install_review_workspace_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "review_workspace_routes_installed", False):
        return
    app.state.review_workspace_routes_installed = True

    service = ValidatedReviewWorkspaceService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ValidatedReviewWorkspaceService:
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

    def target_brand_id(target_type: ReviewTarget, target_id: UUID) -> str:
        content_id = require_service().target_content_id(
            target_type=target_type,
            target_id=target_id,
        )
        return content_brand_id(content_id)

    def invoke(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return call()
        except ReviewWorkspaceError as exc:
            raise_review_workspace_error(exc)
        except psycopg.Error as exc:
            message = str(exc).splitlines()[0][:500]
            raise HTTPException(
                status_code=422,
                detail={"code": "review_workspace_integrity_violation", "message": message},
            ) from exc

    @app.get("/review/inbox")
    def review_inbox(
        brand_id: list[UUID] = Query(default=[]),
        stage: list[str] = Query(default=[]),
        assignee_operator_id: str | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        status: list[str] = Query(default=[]),
        blocker: bool | None = None,
        overdue: bool | None = None,
        item_type: list[str] = Query(default=[]),
        limit: int = 100,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        filters = InboxFilters(
            brand_ids=tuple(brand_id),
            stages=tuple(stage),
            assignee_operator_id=assignee_operator_id,
            due_from=due_from,
            due_to=due_to,
            statuses=tuple(status),
            blocker=blocker,
            overdue=overdue,
            item_types=tuple(item_type),
            limit=limit,
        )
        rows = require_service().inbox(
            filters=filters,
            allowed_brand_ids=(
                None
                if operator.is_admin
                else [UUID(value) for value in visible_brand_ids(operator) or ()]
            ),
        )
        return {"ok": True, "operator": operator.operator_id, "items": rows}

    @app.get("/review/content/{content_id}")
    def content_review_workspace(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=content_brand_id(content_id),
        )
        result = invoke(lambda: require_service().workspace(content_id=content_id))
        return {"operator": operator.operator_id, **result}

    @app.post("/review/compare")
    def compare_review_versions(
        request: CompareTarget,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=target_brand_id(request.target_type, request.current_id),
        )
        if request.previous_id is not None:
            previous_brand = target_brand_id(request.target_type, request.previous_id)
            if previous_brand != target_brand_id(request.target_type, request.current_id):
                raise HTTPException(status_code=422, detail="comparison_target_brand_mismatch")
        result = invoke(lambda: require_service().compare(request=request))
        return {"operator": operator.operator_id, **result}

    @app.post("/review/comments")
    def create_review_comment(
        request: ReviewCommentRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = target_brand_id(request.target_type, request.target_id)
        if operator.is_admin or OperatorRole.REVIEWER in operator.roles:
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
            if request.blocking or request.revision_task is not None:
                raise HTTPException(
                    status_code=403,
                    detail="producer_cannot_create_revision_task",
                )
        else:
            raise HTTPException(status_code=403, detail="review_comment_permission_denied")
        result = invoke(
            lambda: require_service().create_comment(
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/review/comments/{comment_id}/resolve")
    def resolve_review_comment(
        comment_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        context = invoke(lambda: {"ok": True, "context": require_service().comment_context(comment_id=comment_id)})[
            "context"
        ]
        brand_id = str(context["brand_id"])
        if operator.is_admin or OperatorRole.REVIEWER in operator.roles:
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        else:
            raise HTTPException(status_code=403, detail="review_comment_resolution_permission_denied")
        result = invoke(
            lambda: require_service().resolve_comment(
                comment_id=comment_id,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/review/tasks/{task_id}")
    def mutate_revision_task(
        task_id: UUID,
        request: TaskMutationRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        context = invoke(lambda: {"ok": True, "context": require_service().task_context(task_id=task_id)})[
            "context"
        ]
        brand_id = str(context["brand_id"])
        if operator.is_admin or OperatorRole.REVIEWER in operator.roles:
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
            if str(context["assignee_operator_id"]) != operator.operator_id:
                raise HTTPException(status_code=403, detail="revision_task_assignee_required")
            if request.status is None:
                raise HTTPException(status_code=403, detail="producer_can_update_task_status_only")
        else:
            raise HTTPException(status_code=403, detail="revision_task_permission_denied")
        result = invoke(
            lambda: require_service().mutate_task(
                task_id=task_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}


def raise_review_workspace_error(exc: ReviewWorkspaceError) -> None:
    if exc.code in {
        "content_not_found",
        "production_workflow_not_found",
        "review_target_not_found",
        "revision_task_not_found",
        "review_comment_not_found",
        "review_comment_not_found_or_resolved",
    }:
        status_code = 404
    elif exc.code in {"revision_task_conflict"}:
        status_code = 409
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
