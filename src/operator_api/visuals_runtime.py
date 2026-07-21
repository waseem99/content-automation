from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.application.visuals.models import (
    CandidateDecisionRequest,
    CandidateResult,
    ProjectDecisionRequest,
    ResolveReviewActionRequest,
    ReviewActionRequest,
    ShotDecisionRequest,
    ShotRevisionRequest,
    SubmitProjectRequest,
    VisualPresetRequest,
    VisualProjectInitializeRequest,
)
from src.application.visuals.preset_service import VisualPresetError, VisualPresetService
from src.application.visuals.review_service import VisualReviewService
from src.application.visuals.service import VisualProjectError
from src.application.visuals.validated_service import ValidatedVisualProjectService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_visual_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "visual_routes_installed", False):
        return
    app.state.visual_routes_installed = True

    projects = ValidatedVisualProjectService(database) if database is not None else None
    reviews = VisualReviewService(database) if database is not None else None
    presets = VisualPresetService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def require_projects() -> ValidatedVisualProjectService:
        if projects is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return projects

    def require_reviews() -> VisualReviewService:
        if reviews is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return reviews

    def require_presets() -> VisualPresetService:
        if presets is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return presets

    def _brand_id(query: str, values: tuple[Any, ...], *, missing: str) -> str:
        with require_database().connection() as conn:
            row = conn.execute(query, values).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=missing)
        return str(row["brand_id"])

    def content_brand_id(content_id: UUID) -> str:
        return _brand_id(
            """SELECT mp.brand_id
               FROM football_brief.portfolio_content pc
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE pc.id=%s""",
            (content_id,),
            missing="content_not_found",
        )

    def profile_brand_id(profile_id: UUID) -> str:
        return _brand_id(
            "SELECT brand_id FROM football_brief.brand_profiles WHERE id=%s",
            (profile_id,),
            missing="brand_profile_not_found",
        )

    def preset_brand_id(preset_id: UUID) -> str:
        return _brand_id(
            """SELECT bp.brand_id
               FROM football_brief.brand_visual_presets bvp
               JOIN football_brief.brand_profiles bp ON bp.id=bvp.brand_profile_id
               WHERE bvp.id=%s""",
            (preset_id,),
            missing="visual_preset_not_found",
        )

    def project_brand_id(project_id: UUID) -> str:
        return _brand_id(
            """SELECT mp.brand_id
               FROM football_brief.visual_projects vp
               JOIN football_brief.portfolio_content pc ON pc.id=vp.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE vp.id=%s""",
            (project_id,),
            missing="visual_project_not_found",
        )

    def candidate_brand_id(candidate_id: UUID) -> str:
        return _brand_id(
            """SELECT mp.brand_id
               FROM football_brief.visual_candidates vc
               JOIN football_brief.visual_shot_versions vsv ON vsv.id=vc.visual_shot_version_id
               JOIN football_brief.visual_shots vs ON vs.id=vsv.visual_shot_id
               JOIN football_brief.visual_projects vp ON vp.id=vs.visual_project_id
               JOIN football_brief.portfolio_content pc ON pc.id=vp.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE vc.id=%s""",
            (candidate_id,),
            missing="visual_candidate_not_found",
        )

    def invoke(call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return call()
        except VisualPresetError as exc:
            raise_visual_error(exc.code, exc.details)
        except VisualProjectError as exc:
            raise_visual_error(exc.code, exc.details)
        except psycopg.Error as exc:
            message = str(exc).splitlines()[0][:500]
            raise HTTPException(
                status_code=422,
                detail={"code": "visual_integrity_violation", "message": message},
            ) from exc

    @app.get("/visual-presets/profiles/{brand_profile_id}")
    def list_visual_presets(
        brand_profile_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=profile_brand_id(brand_profile_id),
        )
        rows = require_presets().list_for_profile(brand_profile_id=brand_profile_id)
        return {"ok": True, "operator": operator.operator_id, "presets": rows}

    @app.post("/visual-presets/profiles/{brand_profile_id}")
    def create_visual_preset(
        brand_profile_id: UUID,
        request: VisualPresetRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.MANAGE_BRANDS,
            brand_id=profile_brand_id(brand_profile_id),
        )
        result = invoke(
            lambda: require_presets().create(
                brand_profile_id=brand_profile_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visual-presets/{preset_id}/activate")
    def activate_visual_preset(
        preset_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.MANAGE_BRANDS,
            brand_id=preset_brand_id(preset_id),
        )
        result = invoke(
            lambda: require_presets().activate(
                preset_id=preset_id,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/content/{content_id}")
    def initialize_visual_project(
        content_id: UUID,
        request: VisualProjectInitializeRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=content_brand_id(content_id),
        )
        result = invoke(
            lambda: require_projects().initialize(
                content_id=content_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.get("/visuals/content/{content_id}")
    def get_content_visual_project(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=content_brand_id(content_id),
        )
        result = invoke(lambda: require_projects().project_for_content(content_id=content_id))
        return {"operator": operator.operator_id, **result}

    @app.get("/visuals/{project_id}")
    def get_visual_project(
        project_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(lambda: require_projects().detail(project_id=project_id))
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/candidates/{candidate_id}/result")
    def register_visual_candidate_result(
        candidate_id: UUID,
        request: CandidateResult,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=candidate_brand_id(candidate_id),
        )
        result = invoke(
            lambda: require_projects().register_candidate_result(
                candidate_id=candidate_id,
                result=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/{project_id}/shots/{shot_id}/review-actions")
    def create_visual_review_action(
        project_id: UUID,
        shot_id: UUID,
        request: ReviewActionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(
            lambda: require_projects().add_review_action(
                project_id=project_id,
                shot_id=shot_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/{project_id}/shots/{shot_id}/review-actions/{action_id}/resolve")
    def resolve_visual_review_action(
        project_id: UUID,
        shot_id: UUID,
        action_id: UUID,
        request: ResolveReviewActionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = project_brand_id(project_id)
        if operator.is_admin or OperatorRole.REVIEWER in operator.roles:
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        else:
            raise HTTPException(status_code=403, detail="visual_review_resolution_permission_denied")
        result = invoke(
            lambda: require_projects().resolve_review_action(
                project_id=project_id,
                shot_id=shot_id,
                action_id=action_id,
                expected_shot_lock_version=request.expected_shot_lock_version,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post(
        "/visuals/{project_id}/shots/{shot_id}/versions/{shot_version_id}/candidates/{candidate_id}/decisions"
    )
    def decide_visual_candidate(
        project_id: UUID,
        shot_id: UUID,
        shot_version_id: UUID,
        candidate_id: UUID,
        request: CandidateDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(
            lambda: require_reviews().decide_candidate(
                project_id=project_id,
                shot_id=shot_id,
                shot_version_id=shot_version_id,
                candidate_id=candidate_id,
                request=request,
                reviewer=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/{project_id}/shots/{shot_id}/versions/{shot_version_id}/decisions")
    def decide_visual_shot(
        project_id: UUID,
        shot_id: UUID,
        shot_version_id: UUID,
        request: ShotDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(
            lambda: require_reviews().decide_shot(
                project_id=project_id,
                shot_id=shot_id,
                shot_version_id=shot_version_id,
                request=request,
                reviewer=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/{project_id}/shots/{shot_id}/revise")
    def revise_visual_shot(
        project_id: UUID,
        shot_id: UUID,
        request: ShotRevisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(
            lambda: require_projects().revise_shot(
                project_id=project_id,
                shot_id=shot_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/{project_id}/submit")
    def submit_visual_project(
        project_id: UUID,
        request: SubmitProjectRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(
            lambda: require_reviews().submit_project(
                project_id=project_id,
                request=request,
                actor=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}

    @app.post("/visuals/{project_id}/decisions")
    def decide_visual_project(
        project_id: UUID,
        request: ProjectDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=project_brand_id(project_id),
        )
        result = invoke(
            lambda: require_reviews().decide_project(
                project_id=project_id,
                request=request,
                reviewer=operator.operator_id,
            )
        )
        return {"operator": operator.operator_id, **result}


def raise_visual_error(code: str, details: dict[str, Any] | None = None) -> None:
    not_found = {
        "brand_profile_not_found",
        "visual_preset_not_found",
        "visual_preset_parent_not_found",
        "visual_project_not_found",
        "visual_shot_not_found",
        "visual_candidate_not_found",
        "visual_review_action_not_found_or_resolved",
    }
    conflicts = {
        "visual_preset_parent_required",
        "visual_preset_parent_is_not_latest",
        "visual_preset_not_draft",
        "visual_preset_activation_conflict",
        "visual_project_already_active",
        "visual_project_conflict",
        "visual_project_not_working",
        "visual_project_not_ready_for_review",
        "visual_shot_conflict",
        "visual_shot_not_revisable",
        "stale_visual_shot_version",
        "stale_visual_review_action",
        "visual_candidate_not_queued",
        "keyframe_job_not_succeeded",
    }
    forbidden = {"operator_inactive_or_missing"}
    if code in not_found:
        status_code = 404
    elif code in conflicts:
        status_code = 409
    elif code in forbidden:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": code, **dict(details or {})})
