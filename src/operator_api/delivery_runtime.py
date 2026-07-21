from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query

from src.application.delivery.models import (
    DeliveryCancelRequest,
    DeliveryClaimRequest,
    DeliveryCreateRequest,
    DeliveryExecuteRequest,
    DeliveryStatus,
    DeliveryTargetRequest,
)
from src.application.delivery.service import PlatformDeliveryError, PlatformDeliveryService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class DeliveryTargetReasonRequest(DeliveryCancelRequest):
    pass


def install_delivery_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "platform_delivery_routes_installed", False):
        return
    app.state.platform_delivery_routes_installed = True
    service = PlatformDeliveryService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> PlatformDeliveryService:
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

    def require_publisher(operator: OperatorIdentity, *, brand_id: str | None = None) -> None:
        if OperatorRole.PUBLISHER not in operator.roles:
            raise HTTPException(status_code=403, detail="publisher_role_required")
        require_access(operator, AccessPermission.DELIVER_RELEASE, brand_id=brand_id)

    def release_brand(release_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.final_releases fr
                   JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE fr.id=%s""",
                (release_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="final_release_not_found")
        return str(row["brand_id"])

    def delivery_brand(delivery_request_id: UUID) -> str:
        with require_database().connection() as conn:
            row = conn.execute(
                """SELECT mp.brand_id
                   FROM football_brief.platform_delivery_requests pdr
                   JOIN football_brief.final_releases fr ON fr.id=pdr.final_release_id
                   JOIN football_brief.portfolio_content pc ON pc.id=fr.portfolio_content_id
                   JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
                   WHERE pdr.id=%s""",
                (delivery_request_id,),
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="delivery_request_not_found")
        return str(row["brand_id"])

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except PlatformDeliveryError as exc:
            status = 409
            if exc.code in {
                "delivery_target_not_found",
                "delivery_request_not_found",
                "final_release_not_found",
            }:
                status = 404
            elif exc.code in {
                "publisher_role_required",
                "operator_inactive_or_missing",
            }:
                status = 403
            elif exc.code in {
                "delivery_release_no_longer_approved",
                "delivery_target_no_longer_executable",
            }:
                status = 422
            raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "platform_delivery_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.get("/delivery-targets")
    def list_delivery_targets(
        include_retired: bool = Query(default=False),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.READ_PORTFOLIO)
        return {
            "ok": True,
            "operator": operator.operator_id,
            "items": require_service().list_targets(include_retired=include_retired),
        }

    @app.post("/delivery-targets")
    def create_delivery_target(
        request: DeliveryTargetRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().create_target(request, actor=operator.operator_id)),
        }

    @app.post("/delivery-targets/{target_id}/activate")
    def activate_delivery_target(
        target_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().activate_target(target_id=target_id, actor=operator.operator_id)),
        }

    @app.post("/delivery-targets/{target_id}/revise")
    def revise_delivery_target(
        target_id: UUID,
        request: DeliveryTargetRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().revise_target(
                    target_id=target_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }

    @app.post("/delivery-targets/{target_id}/unavailable")
    def mark_delivery_target_unavailable(
        target_id: UUID,
        request: DeliveryTargetReasonRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().mark_target_unavailable(
                    target_id=target_id,
                    actor=operator.operator_id,
                    reason=request.rationale,
                )
            ),
        }

    @app.post("/delivery-targets/{target_id}/retire")
    def retire_delivery_target(
        target_id: UUID,
        request: DeliveryTargetReasonRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().retire_target(
                    target_id=target_id,
                    actor=operator.operator_id,
                    reason=request.rationale,
                )
            ),
        }

    @app.get("/deliveries")
    def list_deliveries(
        status: list[DeliveryStatus] = Query(default=[]),
        limit: int = Query(default=100, ge=1, le=500),
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_publisher(operator)
        brand_ids = None if operator.is_admin else [UUID(item) for item in operator.brand_ids]
        items = require_service().list_deliveries(
            brand_ids=brand_ids,
            statuses=[item.value for item in status],
            limit=limit,
        )
        return {"ok": True, "operator": operator.operator_id, "items": items}

    @app.post("/deliveries")
    def create_delivery(
        request: DeliveryCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_publisher(operator, brand_id=release_brand(request.final_release_id))
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().create_delivery(request, actor=operator.operator_id)),
        }

    @app.get("/deliveries/{delivery_request_id}")
    def delivery_detail(
        delivery_request_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_publisher(operator, brand_id=delivery_brand(delivery_request_id))
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().detail(delivery_request_id=delivery_request_id)),
        }

    @app.post("/deliveries/claim")
    def claim_delivery(
        request: DeliveryClaimRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_publisher(operator)
        if request.worker_id != operator.operator_id:
            raise HTTPException(status_code=403, detail="delivery_worker_identity_mismatch")
        result = invoke(
            lambda: require_service().claim_due(
                request,
                allowed_brand_ids=[UUID(item) for item in operator.brand_ids],
            )
        )
        return {
            "ok": True,
            "operator": operator.operator_id,
            "claimed": result,
        }

    @app.post("/deliveries/{delivery_request_id}/execute")
    def execute_delivery(
        delivery_request_id: UUID,
        request: DeliveryExecuteRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_publisher(operator, brand_id=delivery_brand(delivery_request_id))
        if request.delivery_request_id != delivery_request_id:
            raise HTTPException(status_code=422, detail="delivery_request_id_mismatch")
        if request.worker_id != operator.operator_id:
            raise HTTPException(status_code=403, detail="delivery_worker_identity_mismatch")
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().execute_claim(request)),
        }

    @app.post("/deliveries/{delivery_request_id}/cancel")
    def cancel_delivery(
        delivery_request_id: UUID,
        request: DeliveryCancelRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_publisher(operator, brand_id=delivery_brand(delivery_request_id))
        return {
            "operator": operator.operator_id,
            **invoke(
                lambda: require_service().cancel_delivery(
                    delivery_request_id=delivery_request_id,
                    request=request,
                    actor=operator.operator_id,
                )
            ),
        }
