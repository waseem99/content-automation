from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, HTTPException

from src.application.acceptance.models import (
    DefectOpenRequest,
    DefectResolveRequest,
    LiveDeliveryEvidenceRequest,
    OperationsEvidenceRequest,
    PilotCreateRequest,
    PilotItemRequest,
    SignoffRequest,
)
from src.application.acceptance.service import AcceptancePilotError, AcceptancePilotService
from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


def install_acceptance_routes(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "acceptance_routes_installed", False):
        return
    app.state.acceptance_routes_installed = True
    service = AcceptancePilotService(database) if database is not None else None
    access = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        return access.identity(operator_id, key_name=key_name) if access is not None else None

    authenticate = build_operator_auth(auth_settings, load_identity)

    def require_service() -> AcceptancePilotService:
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        return service

    def require_admin(operator: OperatorIdentity) -> None:
        if not operator.is_admin:
            raise HTTPException(status_code=403, detail="admin_required")
        require_access(operator, AccessPermission.MANAGE_BRANDS)

    def require_role(operator: OperatorIdentity, role: OperatorRole) -> None:
        if role not in operator.roles:
            raise HTTPException(status_code=403, detail=f"{role.value}_required")

    def invoke(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except AcceptancePilotError as exc:
            status = 409
            if exc.code in {"pilot_not_found", "pilot_item_not_found", "pilot_content_not_found"}:
                status = 404
            elif exc.code == "pilot_role_required":
                status = 403
            elif exc.code.startswith("pilot_") or exc.code.startswith("operations_"):
                status = 422
            raise HTTPException(status_code=status, detail={"code": exc.code, **exc.details}) from exc
        except psycopg.Error as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "acceptance_pilot_integrity_violation",
                    "message": str(exc).splitlines()[0][:500],
                },
            ) from exc

    @app.post("/acceptance/pilots")
    def create_pilot(
        request: PilotCreateRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().create(request, actor=operator.operator_id))}

    @app.post("/acceptance/pilots/{pilot_id}/items")
    def add_pilot_item(
        pilot_id: UUID,
        request: PilotItemRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().add_item(pilot_id=pilot_id, request=request, actor=operator.operator_id)),
        }

    @app.post("/acceptance/pilots/{pilot_id}/start")
    def start_pilot(
        pilot_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().start(pilot_id=pilot_id, actor=operator.operator_id))}

    @app.get("/acceptance/pilots/{pilot_id}")
    def pilot_detail(
        pilot_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin and not operator.roles.intersection({OperatorRole.REVIEWER, OperatorRole.PUBLISHER}):
            raise HTTPException(status_code=403, detail="acceptance_read_role_required")
        detail = invoke(lambda: require_service().detail(pilot_id=pilot_id))
        required_brands = {str(item["brand_id"]) for item in detail["items"]}
        if not operator.is_admin and not required_brands.issubset(set(operator.brand_ids)):
            raise HTTPException(status_code=403, detail="pilot_brand_scope_required")
        return {"operator": operator.operator_id, **detail}

    @app.post("/acceptance/items/{item_id}/collect")
    def collect_item_evidence(
        item_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            require_role(operator, OperatorRole.REVIEWER)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().collect_item(item_id=item_id, actor=operator.operator_id))}

    @app.post("/acceptance/items/{item_id}/operations-evidence")
    def bind_operations_evidence(
        item_id: UUID,
        request: OperationsEvidenceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().record_operations_evidence(item_id=item_id, request=request, actor=operator.operator_id)),
        }

    @app.post("/acceptance/pilots/{pilot_id}/defects")
    def open_pilot_defect(
        pilot_id: UUID,
        request: DefectOpenRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            require_role(operator, OperatorRole.REVIEWER)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().open_defect(pilot_id=pilot_id, request=request, actor=operator.operator_id)),
        }

    @app.post("/acceptance/defects/{defect_id}/resolve")
    def resolve_pilot_defect(
        defect_id: UUID,
        request: DefectResolveRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        if not operator.is_admin:
            require_role(operator, OperatorRole.REVIEWER)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().resolve_defect(defect_id=defect_id, request=request, actor=operator.operator_id)),
        }

    @app.post("/acceptance/pilots/{pilot_id}/signoffs")
    def signoff_pilot(
        pilot_id: UUID,
        request: SignoffRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        expected = OperatorRole(request.role.value)
        require_role(operator, expected)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().signoff(pilot_id=pilot_id, request=request, actor=operator.operator_id)),
        }

    @app.post("/acceptance/pilots/{pilot_id}/live-delivery-evidence")
    def record_live_delivery_evidence(
        pilot_id: UUID,
        request: LiveDeliveryEvidenceRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_role(operator, OperatorRole.PUBLISHER)
        return {
            "operator": operator.operator_id,
            **invoke(lambda: require_service().record_live_delivery(pilot_id=pilot_id, request=request, actor=operator.operator_id)),
        }

    @app.post("/acceptance/pilots/{pilot_id}/accept")
    def accept_pilot(
        pilot_id: UUID,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_admin(operator)
        return {"operator": operator.operator_id, **invoke(lambda: require_service().accept(pilot_id=pilot_id, actor=operator.operator_id))}
