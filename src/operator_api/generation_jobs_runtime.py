from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from src.application.generation_jobs.legacy_adapter import import_legacy_records
from src.application.generation_jobs.models import (
    GenerationJobCompletion,
    GenerationJobEnqueue,
    GenerationJobFailure,
    GenerationJobHeartbeat,
    GenerationJobStatus,
    GenerationJobType,
    LegacyGenerationRecord,
)
from src.application.generation_jobs.service import GenerationJobError
from src.operations.job_logging import ObservedGenerationJobService as GenerationJobService
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


class WorkerClaimRequest(BaseModel):
    lease_seconds: int = Field(default=120, ge=15, le=3600)
    job_types: tuple[GenerationJobType, ...] = ()
    providers: tuple[str, ...] = ()


class WorkerHeartbeatRequest(BaseModel):
    attempt_id: UUID
    lease_token: UUID
    lease_seconds: int = Field(default=120, ge=15, le=3600)


class WorkerCompletionRequest(BaseModel):
    attempt_id: UUID
    lease_token: UUID
    output_payload: dict[str, Any]
    actual_cost_usd: float = Field(default=0, ge=0)
    provider_request_id: str | None = Field(default=None, max_length=240)


class WorkerFailureRequest(BaseModel):
    attempt_id: UUID
    lease_token: UUID
    error_code: str = Field(min_length=1, max_length=120)
    error_message: str = Field(min_length=1, max_length=5000)
    retryable: bool
    actual_cost_usd: float = Field(default=0, ge=0)
    error_details: dict[str, Any] = Field(default_factory=dict)


class JobCancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=5000)


class JobRetryRequest(BaseModel):
    delay_seconds: int = Field(default=0, ge=0, le=86400)


class StaleRecoveryRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=1000)


class LegacyImportRequest(BaseModel):
    content_id: UUID
    content_version: int = Field(ge=1)
    source_name: str = Field(default="p68-file-ledger", min_length=1, max_length=120)
    records: list[LegacyGenerationRecord] = Field(min_length=1, max_length=1000)


def install_generation_job_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "generation_job_routes_installed", False):
        return
    app.state.generation_job_routes_installed = True
    service = GenerationJobService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> GenerationJobService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def content_brand_id(content_id: UUID) -> str:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        with database.connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id FROM football_brief.portfolio_content pc
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pc.id=%s""",
                (content_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="content_not_found")
        return str(row["brand_id"])

    def job_detail(job_id: UUID) -> dict[str, Any]:
        try:
            return require_service().detail(job_id=job_id)
        except GenerationJobError as exc:
            raise_generation_error(exc)

    def require_job_permission(
        job_id: UUID,
        operator: OperatorIdentity,
        *,
        read_only: bool = False,
    ) -> dict[str, Any]:
        detail = job_detail(job_id)
        job = detail["job"]
        permission = (
            AccessPermission.READ_PORTFOLIO
            if read_only
            else permission_for_job_type(GenerationJobType(job["job_type"]))
        )
        require_access(operator, permission, brand_id=str(job["brand_id"]))
        return detail

    @app.post("/generation/jobs")
    def enqueue_job(
        request: GenerationJobEnqueue,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        brand_id = content_brand_id(request.portfolio_content_id)
        require_access(operator, permission_for_job_type(request.job_type), brand_id=brand_id)
        try:
            job = require_service().enqueue(request, actor=operator.operator_id)
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"ok": True, "operator": operator.operator_id, "job": job}

    @app.get("/generation/jobs")
    def list_jobs(
        operator: OperatorIdentity = Depends(authenticate),
        status: list[GenerationJobStatus] = Query(default=[]),
        job_type: list[GenerationJobType] = Query(default=[]),
        worker_id: str | None = Query(default=None, max_length=200),
        content_id: UUID | None = None,
        brand_id: UUID | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        if brand_id is not None:
            require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
            brand_ids: list[UUID] | None = [brand_id]
        else:
            visible = visible_brand_ids(operator)
            brand_ids = None if visible is None else [UUID(value) for value in visible]
        try:
            items = require_service().list_jobs(
                brand_ids=brand_ids,
                statuses=status,
                job_types=job_type,
                worker_id=worker_id,
                content_id=content_id,
                limit=limit,
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"ok": True, "operator": operator.operator_id, "count": len(items), "items": items}

    @app.get("/generation/jobs/{job_id}")
    def get_job(
        job_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        detail = require_job_permission(job_id, operator, read_only=True)
        return {"operator": operator.operator_id, **detail}

    @app.post("/generation/jobs/claim")
    def claim_job(
        request: WorkerClaimRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        allowed_types = allowed_worker_job_types(operator)
        if not allowed_types:
            raise HTTPException(status_code=403, detail="worker_role_required")
        visible = visible_brand_ids(operator)
        brand_ids = None if visible is None else [UUID(value) for value in visible]
        try:
            claim = require_service().claim(
                worker_id=operator.operator_id,
                allowed_brand_ids=brand_ids,
                allowed_job_types=allowed_types,
                requested_job_types=request.job_types,
                providers=request.providers,
                lease_seconds=request.lease_seconds,
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"ok": True, "operator": operator.operator_id, "claim": claim}

    @app.post("/generation/jobs/{job_id}/heartbeat")
    def heartbeat_job(
        job_id: UUID,
        request: WorkerHeartbeatRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_job_permission(job_id, operator)
        try:
            result = require_service().heartbeat(
                GenerationJobHeartbeat(
                    job_id=job_id,
                    attempt_id=request.attempt_id,
                    lease_token=request.lease_token,
                    worker_id=operator.operator_id,
                    lease_seconds=request.lease_seconds,
                )
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/generation/jobs/{job_id}/complete")
    def complete_job(
        job_id: UUID,
        request: WorkerCompletionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_job_permission(job_id, operator)
        try:
            result = require_service().complete(
                GenerationJobCompletion(
                    job_id=job_id,
                    attempt_id=request.attempt_id,
                    lease_token=request.lease_token,
                    worker_id=operator.operator_id,
                    output_payload=request.output_payload,
                    actual_cost_usd=request.actual_cost_usd,
                    provider_request_id=request.provider_request_id,
                )
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/generation/jobs/{job_id}/fail")
    def fail_job(
        job_id: UUID,
        request: WorkerFailureRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_job_permission(job_id, operator)
        try:
            result = require_service().fail(
                GenerationJobFailure(
                    job_id=job_id,
                    attempt_id=request.attempt_id,
                    lease_token=request.lease_token,
                    worker_id=operator.operator_id,
                    error_code=request.error_code,
                    error_message=request.error_message,
                    retryable=request.retryable,
                    actual_cost_usd=request.actual_cost_usd,
                    error_details=request.error_details,
                )
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/generation/jobs/{job_id}/cancel")
    def cancel_job(
        job_id: UUID,
        request: JobCancelRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_job_permission(job_id, operator)
        try:
            result = require_service().cancel(
                job_id=job_id,
                actor=operator.operator_id,
                reason=request.reason,
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/generation/jobs/{job_id}/retry")
    def retry_job(
        job_id: UUID,
        request: JobRetryRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_job_permission(job_id, operator)
        try:
            result = require_service().retry(
                job_id=job_id,
                actor=operator.operator_id,
                delay_seconds=request.delay_seconds,
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/generation/jobs/recover-stale")
    def recover_stale_jobs(
        request: StaleRecoveryRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        try:
            result = require_service().recover_stale(actor=operator.operator_id, limit=request.limit)
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"ok": True, "operator": operator.operator_id, **result}

    @app.post("/generation/jobs/import-legacy")
    def import_legacy_jobs(
        request: LegacyImportRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(
            operator,
            AccessPermission.MANAGE_BRANDS,
            brand_id=content_brand_id(request.content_id),
        )
        try:
            result = import_legacy_records(
                service=require_service(),
                records=request.records,
                content_id=request.content_id,
                content_version=request.content_version,
                actor=operator.operator_id,
                source_name=request.source_name,
            )
        except GenerationJobError as exc:
            raise_generation_error(exc)
        return {"operator": operator.operator_id, **result}


def permission_for_job_type(job_type: GenerationJobType) -> AccessPermission:
    if job_type == GenerationJobType.PUBLISHING:
        return AccessPermission.DELIVER_RELEASE
    return AccessPermission.RUN_PRODUCTION


def allowed_worker_job_types(operator: OperatorIdentity) -> set[GenerationJobType]:
    if operator.is_admin:
        return set(GenerationJobType)
    allowed: set[GenerationJobType] = set()
    if OperatorRole.PRODUCER in operator.roles:
        allowed.update(job_type for job_type in GenerationJobType if job_type != GenerationJobType.PUBLISHING)
    if OperatorRole.PUBLISHER in operator.roles:
        allowed.add(GenerationJobType.PUBLISHING)
    return allowed


def raise_generation_error(exc: GenerationJobError) -> None:
    not_found = {
        "generation_job_not_found",
        "content_not_found",
        "dependency_job_not_found",
    }
    conflicts = {
        "content_version_conflict",
        "content_version_superseded",
        "idempotency_conflict",
        "generation_job_claim_conflict",
        "generation_job_completion_conflict",
        "generation_job_failure_conflict",
        "generation_job_attempt_not_current",
        "generation_job_not_running",
        "generation_attempt_not_running",
        "generation_job_lease_expired",
        "generation_job_terminal",
        "generation_job_not_retryable",
        "generation_job_failure_not_retryable",
        "generation_job_attempt_limit_reached",
    }
    forbidden = {
        "operator_inactive_or_missing",
        "worker_job_type_not_allowed",
        "generation_job_worker_mismatch",
        "generation_job_lease_token_invalid",
    }
    if exc.code in not_found:
        status_code = 404
    elif exc.code in conflicts:
        status_code = 409
    elif exc.code in forbidden:
        status_code = 403
    else:
        status_code = 422
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, **exc.details},
    ) from exc
