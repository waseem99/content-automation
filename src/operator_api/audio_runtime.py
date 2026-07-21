from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException

from src.application.audio.models import (
    AssemblyEnqueueRequest,
    AudioDecisionRequest,
    AudioInitializeRequest,
    AudioTakeResult,
    MixRegistrationRequest,
    MixRevisionRequest,
    PronunciationOverrideRequest,
    ResolveReviewActionRequest,
    ReviewActionRequest,
    SelectTakeRequest,
    SubmitAudioRequest,
)
from src.application.audio.service import AudioProductionError, AudioProductionService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_audio_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "audio_routes_installed", False):
        return
    app.state.audio_routes_installed = True
    service = AudioProductionService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> AudioProductionService:
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

    def production_brand_id(production_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.audio_productions ap
                   JOIN football_brief.portfolio_content pc ON pc.id=ap.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE ap.id=%s""",
                (production_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="audio_production_not_found")
        return str(row["brand_id"])

    def take_brand_id(take_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.audio_segment_takes ast
                   JOIN football_brief.audio_productions ap ON ap.id=ast.audio_production_id
                   JOIN football_brief.portfolio_content pc ON pc.id=ap.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE ast.id=%s""",
                (take_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="audio_take_not_found")
        return str(row["brand_id"])

    @app.post("/audio/content/{content_id}")
    def initialize_audio(
        content_id: UUID,
        request: AudioInitializeRequest,
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
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/audio/content/{content_id}")
    def get_content_audio(
        content_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=content_brand_id(content_id),
        )
        try:
            result = require_service().production_for_content(content_id=content_id)
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/audio/{production_id}")
    def get_audio_production(
        production_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().detail(production_id=production_id)
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/pronunciations")
    def add_pronunciation(
        production_id: UUID,
        request: PronunciationOverrideRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().add_pronunciation_override(
                production_id=production_id,
                request=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/paragraphs/{paragraph_id}/regenerate")
    def regenerate_paragraph(
        production_id: UUID,
        paragraph_id: UUID,
        request: AudioInitializeRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().regenerate_paragraph(
                production_id=production_id,
                paragraph_id=paragraph_id,
                request=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/takes/{take_id}/result")
    def register_take_result(
        take_id: UUID,
        request: AudioTakeResult,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=take_brand_id(take_id),
        )
        try:
            result = require_service().register_take_result(
                take_id=take_id,
                result=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/takes/{take_id}/select")
    def select_take(
        production_id: UUID,
        take_id: UUID,
        request: SelectTakeRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().select_take(
                production_id=production_id,
                take_id=take_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/mix")
    def register_mix(
        production_id: UUID,
        request: MixRegistrationRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().register_mix(
                production_id=production_id,
                request=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/submit")
    def submit_audio(
        production_id: UUID,
        request: SubmitAudioRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().submit(
                production_id=production_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/review-actions")
    def create_review_action(
        production_id: UUID,
        request: ReviewActionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().add_review_action(
                production_id=production_id,
                request=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/review-actions/{action_id}/resolve")
    def resolve_review_action(
        production_id: UUID,
        action_id: UUID,
        request: ResolveReviewActionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = production_brand_id(production_id)
        if operator.is_admin or OperatorRole.REVIEWER in operator.roles:
            require_access(operator, AccessPermission.REVIEW_CONTENT, brand_id=brand_id)
        elif OperatorRole.PRODUCER in operator.roles:
            require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=brand_id)
        else:
            raise HTTPException(status_code=403, detail="audio_review_resolution_permission_denied")
        try:
            result = require_service().resolve_review_action(
                production_id=production_id,
                action_id=action_id,
                expected_lock_version=request.expected_lock_version,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/decisions")
    def decide_audio(
        production_id: UUID,
        request: AudioDecisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().decide(
                production_id=production_id,
                expected_lock_version=request.expected_lock_version,
                decision=request.decision,
                rationale=request.rationale,
                reviewer=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/revise")
    def revise_mix(
        production_id: UUID,
        request: MixRevisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().revise_mix(
                production_id=production_id,
                request=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/audio/{production_id}/assembly")
    def enqueue_assembly(
        production_id: UUID,
        request: AssemblyEnqueueRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=production_brand_id(production_id),
        )
        try:
            result = require_service().enqueue_assembly(
                production_id=production_id,
                request=request,
                actor=operator.operator_id,
            )
        except AudioProductionError as exc:
            raise_audio_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_audio_error(exc: AudioProductionError) -> None:
    if exc.code in {
        "audio_production_not_found",
        "audio_take_not_found",
        "audio_paragraph_not_found",
    }:
        status_code = 404
    elif exc.code in {
        "audio_production_conflict",
        "audio_production_already_active",
        "audio_production_not_writable",
        "audio_take_not_queued",
        "audio_take_not_selectable",
        "audio_mix_not_working",
        "audio_mix_not_revisable",
        "stale_audio_mix_version",
        "stale_audio_review_action",
        "audio_review_action_not_found_or_resolved",
        "narration_job_not_succeeded",
        "approved_audio_mix_required",
    }:
        status_code = 409
    elif exc.code in {
        "operator_inactive_or_missing",
        "eligible_narration_preset_required",
        "approved_voice_expired",
        "local_kokoro_voice_required",
    }:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
