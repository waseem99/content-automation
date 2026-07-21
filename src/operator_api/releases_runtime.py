from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.generation_jobs.service import GenerationJobError
from src.application.releases.models import (
    AssemblyEnqueueRequest,
    AssemblyOutputRequest,
    FinalReleaseCreate,
    PlaybackReviewRequest,
    QaEvaluateRequest,
    ReleaseDecisionRequest,
    ReleaseInputApprovalRequest,
    RenderProfileRequest,
)
from src.application.releases.service import FinalReleaseError
from src.application.releases.validated_service import ValidatedFinalReleaseService
from src.infrastructure.database.connection import Database
from src.operator_api.access import AccessPermission, OperatorAccessService, OperatorIdentity, require_access
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_release_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "final_release_routes_installed", False):
        return
    app.state.final_release_routes_installed = True
    service = ValidatedFinalReleaseService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> ValidatedFinalReleaseService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)

    def content_brand(content_id: UUID) -> str:
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

    def release_brand(release_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.final_releases fr
                   JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE fr.id=%s""",
                (release_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="final_release_not_found")
        return str(row["brand_id"])

    def artifact_brand(artifact_version_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                "SELECT brand_id FROM football_brief.shared_artifact_versions WHERE id=%s",
                (artifact_version_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="shared_artifact_not_found")
        return str(row["brand_id"])

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except FinalReleaseError as exc:
            status = 404 if exc.code in {
                "final_release_not_found",
                "render_profile_not_found",
                "release_input_artifact_not_found",
            } else 409
            if exc.code in {"operator_inactive_or_missing"}:
                status = 403
            if exc.code in {
                "release_input_not_current_and_approved",
                "final_release_inputs_superseded_or_unapproved",
                "final_release_blocking_qa_failures",
                "final_release_has_open_blocking_revision_tasks",
            }:
                status = 422
            raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc
        except GenerationJobError as exc:
            raise HTTPException(status_code=409, detail={"code": exc.code, **exc.details}) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "final_release_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/release-profiles")
    def list_release_profiles(
        include_retired: bool = Query(default=False),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        items = require_service().list_profiles(include_retired=include_retired)
        return {"ok": True, "operator": operator.operator_id, "items": items}

    @app.post("/release-profiles")
    def create_release_profile(
        request: RenderProfileRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().create_profile(request, actor=operator.operator_id))}

    @app.post("/release-profiles/{profile_id}/activate")
    def activate_release_profile(
        profile_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().activate_profile(profile_id=profile_id, actor=operator.operator_id))}

    @app.post("/release-profiles/{profile_id}/revise")
    def revise_release_profile(
        profile_id: UUID,
        request: RenderProfileRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().revise_profile(profile_id=profile_id, request=request, actor=operator.operator_id))}

    @app.post("/release-input-decisions")
    def decide_release_input(
        request: ReleaseInputApprovalRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = artifact_brand(request.artifact_version_id)
        require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().decide_input(request, actor=operator.operator_id))}

    @app.get("/releases")
    def list_releases(
        content_id: UUID | None = Query(default=None),
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if content_id:
            require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=content_brand(content_id))
        elif not operator.is_admin:
            raise HTTPException(status_code=422, detail="content_id_required_for_non_admin")
        else:
            require_access(operator, AccessPermission.READ_PORTFOLIO)
        items = require_service().list_releases(content_id=content_id, limit=limit)
        return {"ok": True, "operator": operator.operator_id, "items": items}

    @app.post("/releases")
    def create_release(
        request: FinalReleaseCreate,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=content_brand(request.portfolio_content_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().create_release(request, actor=operator.operator_id))}

    @app.get("/releases/{release_id}")
    def release_detail(
        release_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().detail(release_id=release_id))}

    @app.post("/releases/{release_id}/assembly")
    def enqueue_release_assembly(
        release_id: UUID,
        request: AssemblyEnqueueRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().enqueue_assembly(release_id=release_id, request=request, actor=operator.operator_id))}

    @app.post("/releases/{release_id}/assembly-output")
    def register_release_output(
        release_id: UUID,
        request: AssemblyOutputRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().register_assembly_output(release_id=release_id, request=request, actor=operator.operator_id))}

    @app.post("/releases/{release_id}/qa")
    def evaluate_release_qa(
        release_id: UUID,
        request: QaEvaluateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().evaluate_qa(release_id=release_id, request=request, actor=operator.operator_id))}

    @app.post("/releases/{release_id}/submit-review")
    def submit_release_review(
        release_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().submit_playback_review(release_id=release_id, actor=operator.operator_id))}

    @app.post("/releases/{release_id}/playback-review")
    def record_release_playback_review(
        release_id: UUID,
        request: PlaybackReviewRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().record_playback_review(release_id=release_id, request=request, reviewer=operator.operator_id))}

    @app.post("/releases/{release_id}/decision")
    def decide_release(
        release_id: UUID,
        request: ReleaseDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=release_brand(release_id))
        return {"operator": operator.operator_id, **invoke(lambda: require_service().decide_release(release_id=release_id, request=request, reviewer=operator.operator_id))}
