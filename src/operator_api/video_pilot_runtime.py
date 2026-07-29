from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.video_pilot.grouped_service import GroupedVideoPilotService
from src.application.video_pilot.models import (
    ModelUsePreflightRequest,
    PilotAttemptCompleteRequest,
    PilotAttemptCreateRequest,
    PilotAttemptReviewRequest,
    PilotCaseCreateRequest,
    PilotItemCreateRequest,
    PilotRunCreateRequest,
    PilotRunStartRequest,
)
from src.application.video_pilot.service import VideoPilotError
from src.infrastructure.database.connection import Database
from src.operator_api.access import AccessPermission, OperatorAccessService, OperatorIdentity, require_access
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_video_pilot_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "video_pilot_routes_installed", False):
        return
    app.state.video_pilot_routes_installed = True
    service = GroupedVideoPilotService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> GroupedVideoPilotService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def admin_required(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")

    @app.get("/video-pilot/model-use-matrix")
    def model_use_matrix(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        return {"operator": operator.operator_id, **require_service().model_use_matrix()}

    @app.post("/video-pilot/model-use-preflight")
    def model_use_preflight(
        request: ModelUsePreflightRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().model_use_preflight(request)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/runs")
    def create_run(
        request: PilotRunCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        admin_required(operator)
        try:
            result = require_service().create_run(request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/video-pilot/runs")
    def list_runs(
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        try:
            result = require_service().list_runs(limit=limit)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/video-pilot/runs/{run_id}")
    def run_detail(
        run_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        try:
            result = require_service().detail(run_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/runs/{run_id}/start")
    def start_run(
        run_id: UUID,
        request: PilotRunStartRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        admin_required(operator)
        try:
            result = require_service().start_run(run_id, request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/runs/{run_id}/items")
    def create_item(
        run_id: UUID,
        request: PilotItemCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().create_item(run_id, request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/runs/{run_id}/cases")
    def create_case(
        run_id: UUID,
        request: PilotCaseCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().create_case(run_id, request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/cases/{case_id}/attempts")
    def create_attempt(
        case_id: UUID,
        request: PilotAttemptCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().create_attempt(case_id, request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/attempts/{attempt_id}/complete")
    def complete_attempt(
        attempt_id: UUID,
        request: PilotAttemptCompleteRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION)
        try:
            result = require_service().complete_attempt(attempt_id, request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/attempts/{attempt_id}/reviews")
    def review_attempt(
        attempt_id: UUID,
        request: PilotAttemptReviewRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.REVIEW_CONTENT)
        try:
            result = require_service().review_attempt(attempt_id, request, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/video-pilot/runs/{run_id}/report")
    def report_preview(
        run_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        try:
            result = require_service().report(run_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/runs/{run_id}/report-snapshots")
    def snapshot_report(
        run_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        admin_required(operator)
        try:
            result = require_service().snapshot_report(run_id, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/video-pilot/runs/{run_id}/close")
    def close_run(
        run_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        admin_required(operator)
        try:
            result = require_service().close_run(run_id, actor=operator.operator_id)
        except VideoPilotError as exc:
            raise_video_pilot_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_video_pilot_error(exc: VideoPilotError) -> None:
    if exc.code.endswith("_not_found"):
        status_code = 404
    elif exc.code in {
        "pilot_run_key_exists",
        "pilot_item_key_exists",
        "pilot_case_key_exists",
        "pilot_attempt_already_terminal",
        "pilot_case_already_has_accepted_output",
    }:
        status_code = 409
    elif exc.code in {
        "video_model_use_not_allowed",
        "pilot_snapshot_contains_sensitive_field",
    }:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(status_code=status_code, detail={"code": exc.code, **exc.details}) from exc


__all__ = ["install_video_pilot_routes"]
