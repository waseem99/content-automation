from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.concepts.models import (
    CandidateReviewRequest,
    CandidateRevisionRequest,
    ConceptBatchRequest,
    SlateApplyRequest,
    SlateBuildRequest,
)
from src.application.concepts.safe_service import SafeConceptGenerationService
from src.application.concepts.service import ConceptServiceError
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    require_access,
    visible_brand_ids,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_concept_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "concept_routes_installed", False):
        return
    app.state.concept_routes_installed = True
    service = SafeConceptGenerationService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> SafeConceptGenerationService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_database() -> Database:
        if database is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return database

    def batch_brand_id(batch_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                "SELECT brand_id FROM football_brief.concept_generation_batches WHERE id=%s",
                (batch_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="concept_batch_not_found")
        return str(row["brand_id"])

    def candidate_brand_id(candidate_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT gb.brand_id
                   FROM football_brief.concept_candidates c
                   JOIN football_brief.concept_generation_batches gb ON gb.id=c.batch_id
                   WHERE c.id=%s""",
                (candidate_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="concept_candidate_not_found")
        return str(row["brand_id"])

    def slate_brand_id(slate_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT gb.brand_id
                   FROM football_brief.concept_slates s
                   JOIN football_brief.concept_generation_batches gb ON gb.id=s.batch_id
                   WHERE s.id=%s""",
                (slate_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="concept_slate_not_found")
        return str(row["brand_id"])

    @app.post("/concepts/batches")
    def generate_concept_batch(
        request: ConceptBatchRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.RUN_PRODUCTION, brand_id=str(request.brand_id))
        try:
            result = require_service().generate_batch(request, actor=operator.operator_id)
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/concepts/batches")
    def list_concept_batches(
        operator: OperatorIdentity = Depends(authenticate),
        brand_id: UUID | None = None,
        month_start: date | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        if brand_id is not None:
            require_access(operator, AccessPermission.READ_PORTFOLIO, brand_id=str(brand_id))
            brand_ids: list[UUID] | None = [brand_id]
        else:
            visible = visible_brand_ids(operator)
            brand_ids = None if visible is None else [UUID(value) for value in visible]
        try:
            items = require_service().list_batches(
                brand_ids=brand_ids,
                month_start=month_start,
                limit=limit,
            )
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {
            "ok": True,
            "operator": operator.operator_id,
            "count": len(items),
            "items": items,
        }

    @app.get("/concepts/batches/{batch_id}")
    def get_concept_batch(
        batch_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=batch_brand_id(batch_id),
        )
        try:
            result = require_service().batch_detail(batch_id=batch_id)
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/concepts/candidates/{candidate_id}/review")
    def review_concept_candidate(
        candidate_id: UUID,
        request: CandidateReviewRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=candidate_brand_id(candidate_id),
        )
        try:
            result = require_service().review_candidate(
                candidate_id=candidate_id,
                action=request.action,
                rationale=request.rationale,
                actor=operator.operator_id,
            )
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/concepts/candidates/{candidate_id}/revise")
    def revise_concept_candidate(
        candidate_id: UUID,
        request: CandidateRevisionRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.RUN_PRODUCTION,
            brand_id=candidate_brand_id(candidate_id),
        )
        try:
            result = require_service().revise_candidate(
                candidate_id=candidate_id,
                request=request,
                actor=operator.operator_id,
            )
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/concepts/slates")
    def build_concept_slate(
        request: SlateBuildRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=batch_brand_id(request.batch_id),
        )
        try:
            result = require_service().build_slate(request, actor=operator.operator_id)
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.get("/concepts/slates/{slate_id}")
    def get_concept_slate(
        slate_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.READ_PORTFOLIO,
            brand_id=slate_brand_id(slate_id),
        )
        try:
            result = require_service().slate_detail(slate_id=slate_id)
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/concepts/slates/{slate_id}/approve")
    def approve_concept_slate(
        slate_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(
            operator,
            AccessPermission.REVIEW_CONTENT,
            brand_id=slate_brand_id(slate_id),
        )
        try:
            result = require_service().approve_slate(
                slate_id=slate_id,
                actor=operator.operator_id,
            )
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}

    @app.post("/concepts/slates/{slate_id}/apply")
    def apply_concept_slate(
        slate_id: UUID,
        request: SlateApplyRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(
            operator,
            AccessPermission.MANAGE_BRANDS,
            brand_id=slate_brand_id(slate_id),
        )
        try:
            result = require_service().apply_slate(
                slate_id=slate_id,
                request=request,
                actor=operator.operator_id,
            )
        except ConceptServiceError as exc:
            raise_concept_error(exc)
        return {"operator": operator.operator_id, **result}


def raise_concept_error(exc: ConceptServiceError) -> None:
    not_found = {
        "concept_batch_not_found",
        "concept_candidate_not_found",
        "concept_slate_not_found",
        "monthly_plan_not_found",
    }
    conflicts = {
        "concept_candidate_terminal",
        "concept_candidate_not_revisable",
        "concept_slate_not_approvable",
        "concept_slate_not_approved",
        "concept_slate_approval_conflict",
        "concept_slate_application_conflict",
        "concept_slate_item_application_conflict",
        "concept_candidate_application_conflict",
        "candidate_became_duplicate",
        "concept_batch_not_slate_ready",
        "monthly_plan_not_draft",
        "monthly_plan_target_exceeded",
        "slate_schedule_candidate_mismatch",
        "concept_slate_plan_mismatch",
        "concept_slate_incomplete",
        "concept_slate_candidate_status_invalid",
        "concept_slate_distribution_gap",
    }
    forbidden = {
        "operator_inactive_or_missing",
        "active_brand_profile_required",
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
