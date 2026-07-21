from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.requests import Request

from src.infrastructure.database.connection import Database
from src.operator_api.access import (
    AccessPermission,
    OperatorAccessService,
    OperatorIdentity,
    OperatorRole,
    require_access,
)
from src.operator_api.auth import OperatorAuthSettings, build_operator_auth


class OperatorUserRequest(BaseModel):
    operator_id: str = Field(min_length=3, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=200)
    active: bool = True
    roles: list[OperatorRole] = Field(min_length=1, max_length=4)
    brand_ids: list[UUID] = Field(default_factory=list, max_length=100)


def install_operator_access(
    app: FastAPI,
    *,
    database: Database | None,
    auth_settings: OperatorAuthSettings,
) -> None:
    if getattr(app.state, "operator_access_installed", False):
        return
    app.state.operator_access_installed = True
    service = OperatorAccessService(database) if database is not None else None

    def load_identity(operator_id: str, key_name: str) -> OperatorIdentity | None:
        if service is None:
            return None
        return service.identity(operator_id, key_name=key_name)

    authenticate = build_operator_auth(auth_settings, load_identity)

    @app.middleware("http")
    async def operator_access_middleware(request: Request, call_next):
        permission = _required_permission(request.method, request.url.path)
        if permission is None:
            return await call_next(request)
        try:
            identity = authenticate(request)
            request.state.operator_identity = identity
            brand_ids = await _request_brand_ids(request, database)
            if not identity.is_admin and _brand_is_required(request.method, request.url.path) and not brand_ids:
                raise HTTPException(status_code=403, detail="brand_scope_required")
            require_access(identity, permission)
            for brand_id in brand_ids:
                require_access(identity, permission, brand_id=brand_id)
            if permission == AccessPermission.REVIEW_CONTENT:
                await _prevent_self_approval(request, database, identity)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        response = await call_next(request)
        if identity.is_admin or response.status_code >= 400:
            return response
        return await _filter_response_for_brand_scope(response, request.url.path, identity)

    def list_operators(operator: OperatorIdentity = Depends(authenticate)) -> dict[str, Any]:
        require_access(operator, AccessPermission.MANAGE_USERS)
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        users = service.list_users()
        return {"ok": True, "operator": operator.operator_id, "count": len(users), "users": users}

    def upsert_operator(
        request: OperatorUserRequest,
        operator: OperatorIdentity = Depends(authenticate),
    ) -> dict[str, Any]:
        require_access(operator, AccessPermission.MANAGE_USERS)
        if service is None:
            raise HTTPException(status_code=503, detail="database_not_configured")
        if request.operator_id == operator.operator_id and (
            not request.active or OperatorRole.ADMIN not in request.roles
        ):
            raise HTTPException(status_code=409, detail="admin_cannot_remove_own_access")
        try:
            user = service.upsert_user(
                operator_id=request.operator_id,
                display_name=request.display_name,
                active=request.active,
                roles=(role.value for role in request.roles),
                brand_ids=(str(brand_id) for brand_id in request.brand_ids),
                actor=operator.operator_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "operator": operator.operator_id, "user": user}

    app.add_api_route(
        "/admin/operators",
        list_operators,
        methods=["GET"],
        name="list_operators",
    )
    app.add_api_route(
        "/admin/operators",
        upsert_operator,
        methods=["POST"],
        name="upsert_operator",
    )


def _required_permission(method: str, path: str) -> AccessPermission | None:
    if path.startswith("/admin/operators"):
        return AccessPermission.MANAGE_USERS
    if not path.startswith("/portfolio"):
        return None
    if method == "GET":
        return AccessPermission.READ_PORTFOLIO
    if path == "/portfolio/brands":
        return AccessPermission.MANAGE_BRANDS
    if path.endswith("/approvals"):
        return AccessPermission.REVIEW_CONTENT
    if "/packages/" in path and path.endswith("/metrics"):
        return AccessPermission.DELIVER_RELEASE
    if path.endswith("/packages"):
        return AccessPermission.RUN_PRODUCTION
    if path.endswith("/artifacts") or path.endswith("/workspace"):
        return AccessPermission.RUN_PRODUCTION
    return AccessPermission.EDIT_CONTENT


def _brand_is_required(method: str, path: str) -> bool:
    if method == "GET":
        return bool(re.match(r"^/portfolio/content/[0-9a-fA-F-]+", path))
    if path in {"/portfolio/brands", "/portfolio/references"}:
        return False
    if path.startswith("/portfolio/reference-jobs/"):
        return False
    return True


async def _request_brand_ids(request: Request, database: Database | None) -> set[str]:
    if database is None:
        return set()
    query_brand = request.query_params.get("brand_id")
    if query_brand:
        return {query_brand}
    path = request.url.path
    content_match = re.match(r"^/portfolio/content/([0-9a-fA-F-]+)", path)
    if content_match:
        return _content_brand_ids(database, content_match.group(1))
    package_match = re.match(r"^/portfolio/packages/([0-9a-fA-F-]+)", path)
    if package_match:
        return _package_brand_ids(database, package_match.group(1))
    reference_match = re.match(r"^/portfolio/references/([0-9a-fA-F-]+)", path)
    if reference_match:
        body = await _json_body(request)
        if body.get("brand_id"):
            return {str(body["brand_id"])}
        return _reference_brand_ids(database, reference_match.group(1))
    if request.method != "GET":
        body = await _json_body(request)
        if body.get("brand_id"):
            return {str(body["brand_id"])}
        if body.get("brand_slug"):
            return _brand_ids_for_slug(database, str(body["brand_slug"]))
        if body.get("portfolio_content_id"):
            return _content_brand_ids(database, str(body["portfolio_content_id"]))
    return set()


async def _prevent_self_approval(
    request: Request,
    database: Database | None,
    identity: OperatorIdentity,
) -> None:
    if database is None or not request.url.path.startswith("/portfolio/content/"):
        return
    body = await _json_body(request)
    if body.get("decision") != "approved":
        return
    match = re.match(r"^/portfolio/content/([0-9a-fA-F-]+)/approvals$", request.url.path)
    if not match:
        return
    with database.connection() as conn:
        item = conn.execute(
            "SELECT stage FROM football_brief.portfolio_content WHERE id=%s::uuid",
            (match.group(1),),
        ).fetchone()
        if not item:
            return
        stage = str(item["stage"])
        protected_kinds = {
            "preview": {"voiceover", "preview"},
            "package": {"preview", "final_video", "package"},
        }.get(stage, set())
        if not protected_kinds:
            return
        artifacts = conn.execute(
            """SELECT kind, created_by FROM football_brief.portfolio_content_artifacts
               WHERE portfolio_content_id=%s::uuid AND review_status <> 'superseded'""",
            (match.group(1),),
        ).fetchall()
    if self_review_conflict(
        stage=stage,
        reviewer=identity.operator_id,
        artifacts=[dict(row) for row in artifacts],
    ):
        raise HTTPException(status_code=409, detail="self_review_not_allowed")


def self_review_conflict(*, stage: str, reviewer: str, artifacts: list[dict[str, Any]]) -> bool:
    protected_kinds = {
        "preview": {"voiceover", "preview"},
        "package": {"preview", "final_video", "package"},
    }.get(stage, set())
    return any(
        str(artifact.get("kind")) in protected_kinds
        and str(artifact.get("created_by")) == reviewer
        for artifact in artifacts
    )


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.body()
        value = json.loads(body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _brand_ids_for_slug(database: Database, slug: str) -> set[str]:
    with database.connection() as conn:
        row = conn.execute("SELECT id FROM football_brief.brands WHERE slug=%s", (slug,)).fetchone()
    return {str(row["id"])} if row else set()


def _content_brand_ids(database: Database, content_id: str) -> set[str]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT mp.brand_id FROM football_brief.portfolio_content pc
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE pc.id=%s::uuid""",
            (content_id,),
        ).fetchone()
    return {str(row["brand_id"])} if row else set()


def _package_brand_ids(database: Database, package_id: str) -> set[str]:
    with database.connection() as conn:
        row = conn.execute(
            """SELECT mp.brand_id FROM football_brief.platform_packages pp
               JOIN football_brief.portfolio_content pc ON pc.id=pp.portfolio_content_id
               JOIN football_brief.monthly_content_plans mp ON mp.id=pc.plan_id
               WHERE pp.id=%s::uuid""",
            (package_id,),
        ).fetchone()
    return {str(row["brand_id"])} if row else set()


def _reference_brand_ids(database: Database, source_id: str) -> set[str]:
    with database.connection() as conn:
        rows = conn.execute(
            """SELECT brand_id FROM football_brief.reference_brand_assignments
               WHERE reference_source_id=%s::uuid AND active=true""",
            (source_id,),
        ).fetchall()
    return {str(row["brand_id"]) for row in rows}


async def _filter_response_for_brand_scope(
    response: Response,
    path: str,
    identity: OperatorIdentity,
) -> Response:
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type or not hasattr(response, "body_iterator"):
        return response
    if path not in {"/portfolio/brands", "/portfolio/queue", "/portfolio/readiness", "/portfolio/references"}:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response(content=body, status_code=response.status_code, headers=dict(response.headers), media_type=content_type)
    allowed = identity.brand_ids
    if path == "/portfolio/brands":
        payload["brands"] = [item for item in payload.get("brands", []) if str(item.get("id")) in allowed]
        payload["count"] = len(payload["brands"])
    elif path == "/portfolio/queue":
        payload["items"] = [item for item in payload.get("items", []) if str(item.get("brand_id")) in allowed]
        payload["count"] = len(payload["items"])
    elif path == "/portfolio/readiness":
        payload["brands"] = [item for item in payload.get("brands", []) if str(item.get("brand_id")) in allowed]
        payload["brand_count"] = len(payload["brands"])
        payload["target_count"] = sum(int(item.get("target_count") or 0) for item in payload["brands"])
        payload["planned_count"] = sum(int(item.get("planned_count") or 0) for item in payload["brands"])
        payload["ready_brand_count"] = sum(1 for item in payload["brands"] if item.get("inventory_ready"))
    else:
        def reference_visible(item: dict[str, Any]) -> bool:
            item_brands = item.get("brand_ids") or ([item.get("brand_id")] if item.get("brand_id") else [])
            return any(str(brand_id) in allowed for brand_id in item_brands)
        payload["items"] = [item for item in payload.get("items", []) if reference_visible(item)]
        payload["count"] = len(payload["items"])
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return JSONResponse(content=payload, status_code=response.status_code, headers=headers)
